"""iaMAC — IA própria + Motor de Aprendizado Contínuo (VPS_IA_Generativa_Motor_Aprendizado).

Copiloto do VPS com **grounding/citações** (RAG sobre as specs + estado ao vivo do
sistema), **data flywheel** (coleta interações + feedback → dataset → eval harness
= "verificar ganho") e posicionamento **Mac/MLX** (§10).

Tese do spec: a IA é "sua" por soberania (infra/dados), e fica mais inteligente
pelo **flywheel** (RAG fresco + eval), não por treinar do zero. Aqui o RAG é
EXTRATIVO (sem depender de API externa) — toda resposta cita a fonte; síntese por
LLM (Claude/MLX) é melhoria opcional. Guardrail: só lê/recomenda, nunca altera o passado.
"""
from __future__ import annotations

import platform
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..db.database import get_connection

_ROOT = Path(__file__).resolve().parents[3]   # raiz do projeto (onde estão os .md)
_corpus_cache: list[dict[str, Any]] | None = None

# Golden set p/ o eval harness (pergunta → palavra-chave esperada na resposta/fonte).
_GOLDEN = [
    ("o que é o fio dourado / tag-id", "tag-id"),
    ("como funciona a captura de tela", "tela"),
    ("o que faz o rastreamento de objetos", "track"),
    ("como funciona a termografia preditiva", "hotspot"),
    ("o que é metrologia dimensional", "toler"),
    ("como a IA fica mais inteligente (flywheel)", "flywheel"),
    ("reconhecimento facial respeita LGPD?", "consent"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s)


def _tokens(s: str) -> list[str]:
    return [t for t in _norm(s).split() if len(t) > 2]


# ── Corpus (RAG) ─────────────────────────────────────────────────────
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Separa o cabecalho YAML simples (chave: valor) do corpo.

    Os SKILL.md do GPlanSIS-HSkills declaram name/description/category/layer ali.
    Sem ler isso, os 45 chunks chegariam ao RAG com o titulo "SKILL" e a citacao
    nao diria de qual skill a resposta veio.
    """
    m = _FRONTMATTER.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    return meta, text[m.end():]


def _chunk_md(path: Path, rotulo: str, kind: str) -> list[dict[str, Any]]:
    """Quebra um .md em chunks por cabecalho `## `, preservando a origem."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return []
    meta, body = _frontmatter(text)
    nome = meta.get("name") or path.stem
    desc = meta.get("description") or ""
    extra = " - ".join(x for x in [meta.get("category"), meta.get("layer")] if x)
    out: list[dict[str, Any]] = []
    if desc:
        # A descricao e o que melhor responde "para que serve esta skill".
        out.append({"source": rotulo, "kind": kind, "title": nome,
                    "text": f"{nome} - {desc}" + (f" ({extra})" if extra else "")})
    buf: list[str] = []
    heading = nome
    for line in body.splitlines():
        if line.startswith("## "):
            if buf:
                out.append({"source": rotulo, "kind": kind, "title": f"{nome} - {heading}",
                            "text": "\n".join(buf).strip()})
            heading = line.lstrip("# ").strip()
            buf = []
        else:
            buf.append(line)
    if buf:
        out.append({"source": rotulo, "kind": kind, "title": f"{nome} - {heading}",
                    "text": "\n".join(buf).strip()})
    return out


def _extra_dirs() -> list[Path]:
    csv = get_settings().iamac_corpus_dirs or ""
    return [Path(p.strip()) for p in csv.split(",") if p.strip()]


def biblioteca_dir() -> Path:
    """Pasta gerenciada pela interface (upload/remoção). Criada sob demanda."""
    d = get_settings().iamac_library_dir
    p = Path(d) if d else Path(get_settings().db_path).parent / "biblioteca"
    p.mkdir(parents=True, exist_ok=True)
    return p


# Inventário da última indexação: TODO arquivo visto, lido ou não, com o motivo.
_inventario: list[dict[str, Any]] = []


def _chunk_arquivo(path: Path, rotulo: str, kind: str) -> list[dict[str, Any]]:
    """Qualquer formato → chunks. Markdown mantém a quebra por `## `; o resto
    quebra por parágrafo em ~1400 caracteres; PDF/planilha/slides já chegam
    separados por página/aba/slide e a citação diz qual."""
    from . import leitor
    if path.suffix.lower() == ".md":
        out = _chunk_md(path, rotulo, kind)
        _inventario.append({"source": rotulo, "path": str(path), "kind": kind, "tipo": "Markdown",
                            "bytes": path.stat().st_size if path.exists() else 0,
                            "chunks": len(out), "ok": bool(out), "erro": None if out else "vazio"})
        return out
    meta = leitor.ler(path)
    out: list[dict[str, Any]] = []
    if meta["ok"]:
        for titulo, texto in meta["blocos"]:
            pedacos = leitor.em_pedacos(texto)
            for i, ped in enumerate(pedacos, 1):
                sufixo = f" · {titulo}" if titulo != path.stem else ""
                parte = f" · parte {i}/{len(pedacos)}" if len(pedacos) > 1 else ""
                out.append({"source": rotulo, "kind": kind, "title": f"{path.stem}{sufixo}{parte}", "text": ped})
    _inventario.append({"source": rotulo, "path": str(path), "kind": kind, "tipo": meta["tipo"],
                        "bytes": meta["bytes"], "chunks": len(out), "ok": meta["ok"], "erro": meta["erro"]})
    return out


def _inventario_chunk() -> dict[str, Any]:
    """Um chunk que descreve a própria base: responde "quais arquivos você tem?".

    Sem isto a pergunta caía em trechos aleatórios que citavam a palavra
    "arquivo" — foi o que aconteceu na primeira conversa de teste."""
    lidos = [i for i in _inventario if i["ok"]]
    nao = [i for i in _inventario if not i["ok"]]
    por_kind: dict[str, int] = {}
    for i in lidos:
        por_kind[i["kind"]] = por_kind.get(i["kind"], 0) + 1
    linhas = [f"Inventário da base de conhecimento do iaMAC: {len(lidos)} arquivos indexados "
              f"({', '.join(f'{v} {k}' for k, v in sorted(por_kind.items()))}), "
              f"{sum(i['chunks'] for i in lidos)} trechos; {len(nao)} arquivos não lidos.",
              "Documentos e arquivos disponíveis (fonte · tipo · trechos):"]
    for i in sorted(lidos, key=lambda x: x["source"].lower()):
        linhas.append(f"- {i['source']} · {i['tipo']} · {i['chunks']} trechos")
    if nao:
        linhas.append("Arquivos presentes mas não lidos:")
        for i in nao:
            linhas.append(f"- {i['source']} · {i['tipo']} · {i['erro']}")
    linhas.append("Formatos suportados pelo leitor de documentos: Markdown, texto, CSV, JSON, YAML, XML, HTML, "
                  "código, PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx). A biblioteca aceita upload pela tela do iaMAC.")
    return {"source": "Inventário de documentos", "kind": "live", "title": "Quais arquivos e documentos a base tem",
            "text": "\n".join(linhas)}


def _build_corpus() -> list[dict[str, Any]]:
    from . import leitor
    _inventario.clear()
    chunks: list[dict[str, Any]] = []
    for md in sorted(_ROOT.glob("*.md")):
        chunks += _chunk_arquivo(md, md.name, "spec")
    # Diretórios extra (specs no servidor + GPlanSIS·HSkills) e a biblioteca
    # gerenciável: TODO arquivo suportado entra, não só .md.
    fontes = [(d, "doc") for d in _extra_dirs()] + [(biblioteca_dir(), "biblioteca")]
    for d, kind_padrao in fontes:
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if not f.is_file() or f.name.startswith(".") or "node_modules" in f.parts:
                continue
            if not leitor.suportado(f):
                # aparece no inventário como "não suportado" — o usuário vê que
                # o arquivo está lá e por que a IA não o lê
                _inventario.append({"source": f.name, "path": str(f), "kind": kind_padrao, "tipo": leitor.tipo(f),
                                    "bytes": f.stat().st_size, "chunks": 0, "ok": False,
                                    "erro": f"formato {f.suffix or '(sem extensão)'} não suportado"})
                continue
            eh_skill = f.name.upper() == "SKILL.MD"
            rotulo = f"{f.parent.name}/SKILL.md" if eh_skill else (f.name if kind_padrao == "biblioteca" else f.name)
            chunks += _chunk_arquivo(f, rotulo, "skill" if eh_skill else kind_padrao)
    chunks.append(_inventario_chunk())
    chunks.append(_system_snapshot())
    return [c for c in chunks if c["text"]]


def inventario() -> list[dict[str, Any]]:
    """Todos os arquivos vistos na última indexação (lidos ou não)."""
    corpus()   # garante indexação
    return list(_inventario)


# ── Biblioteca gerenciável ───────────────────────────────────────────
_NOME_OK = re.compile(r"[^A-Za-z0-9._ \-()]+")


def biblioteca_listar() -> list[dict[str, Any]]:
    corpus()
    d = biblioteca_dir()
    por_path = {i["path"]: i for i in _inventario}
    out = []
    for f in sorted(d.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        i = por_path.get(str(f), {})
        out.append({"name": f.name, "bytes": f.stat().st_size, "tipo": i.get("tipo") or f.suffix.lstrip(".").upper(),
                    "chunks": i.get("chunks", 0), "ok": i.get("ok", False), "erro": i.get("erro"),
                    "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()})
    return out


def biblioteca_salvar(nome: str, dados: bytes) -> dict[str, Any]:
    """Grava um arquivo enviado e reindexa. Nome sanitizado: sem caminho, sem
    caracteres estranhos — o nome vem do navegador, não de quem confia nele."""
    from . import leitor
    base = Path(nome).name
    limpo = _NOME_OK.sub("_", base).strip() or "documento"
    dest = biblioteca_dir() / limpo
    if not leitor.suportado(dest):
        return {"ok": False, "message": f"formato {dest.suffix or '(sem extensão)'} não suportado",
                "supported": sorted(leitor.SUPORTADOS)}
    if len(dados) > 40 * 1024 * 1024:
        return {"ok": False, "message": "arquivo maior que 40 MB"}
    dest.write_bytes(dados)
    n = reindex()
    item = next((i for i in _inventario if i["path"] == str(dest)), None)
    try:
        from .. import audit
        audit.record("SYSTEM", "LIBRARY_UPLOAD", actor="iamac", entity_type="document", entity_id=limpo,
                     summary=f"documento adicionado à biblioteca: {limpo} ({(item or {}).get('chunks', 0)} trechos)",
                     payload={"bytes": len(dados), "ok": (item or {}).get("ok"), "erro": (item or {}).get("erro")})
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "name": limpo, "chunks": (item or {}).get("chunks", 0), "lido": (item or {}).get("ok", False),
            "erro": (item or {}).get("erro"), "total_chunks": n}


def biblioteca_remover(nome: str) -> dict[str, Any]:
    base = Path(nome).name
    f = biblioteca_dir() / base
    if not f.is_file():
        return {"ok": False, "message": "arquivo não encontrado"}
    f.unlink()
    n = reindex()
    try:
        from .. import audit
        audit.record("SYSTEM", "LIBRARY_DELETE", actor="iamac", entity_type="document", entity_id=base,
                     summary=f"documento removido da biblioteca: {base}")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "total_chunks": n}
    return [c for c in chunks if c["text"]]


def _system_snapshot() -> dict[str, Any]:
    """Chunk 'ao vivo' — a IA conhece o estado atual (frescor, §4)."""
    lines = ["Estado atual do VisionDesk + VPS (ao vivo):"]
    try:
        from .. import audit
        s = audit.summary()
        lines.append(f"- Trilha de auditoria: {s.get('total_events')} eventos, {s.get('alerts')} alertas; por categoria: {s.get('by_category')}.")
    except Exception:  # noqa: BLE001
        pass
    try:
        from ..vps import store as vstore  # noqa: F401
        n = get_connection().execute("SELECT COUNT(*) AS n FROM vps_event").fetchone()
        tags = get_connection().execute("SELECT COUNT(*) AS n FROM vps_tag").fetchone()
        lines.append(f"- VPS Fio Dourado (runtime): {dict(n)['n']} eventos, {dict(tags)['n']} tags.")
    except Exception:  # noqa: BLE001
        pass
    for tbl, lbl in [("thermal_reading", "leituras térmicas"), ("metro_measurement", "medições"),
                     ("vps_face_template", "biometrias"), ("vps_track_summary", "sumários de track")]:
        try:
            r = get_connection().execute(f"SELECT COUNT(*) AS n FROM {tbl}").fetchone()
            lines.append(f"- {lbl}: {dict(r)['n']}.")
        except Exception:  # noqa: BLE001
            pass
    return {"source": "Estado do Sistema (ao vivo)", "kind": "live", "title": "Snapshot", "text": "\n".join(lines)}


def corpus() -> list[dict[str, Any]]:
    global _corpus_cache
    if _corpus_cache is None:
        _corpus_cache = _build_corpus()
    # snapshot ao vivo sempre atualizado (substitui o último)
    out = [c for c in _corpus_cache if c["source"] != "Estado do Sistema (ao vivo)"]
    return out + [_system_snapshot()]


def _por_kind() -> dict[str, int]:
    """Chunks por origem (spec/skill/doc) e quantas skills distintas entraram.

    "1 chunks" no painel nao diz se o RAG esta vazio ou se o numero e esperado —
    e no primeiro deploy do VPS ele ESTAVA vazio, porque so app/ foi enviado e
    nenhum .md existia no servidor.
    """
    out: dict[str, int] = {}
    skills: set[str] = set()
    for c in corpus():
        k = c.get("kind", "spec")
        out[k] = out.get(k, 0) + 1
        if k == "skill":
            skills.add(c["source"])
    out["skills_distintas"] = len(skills)
    out["arquivos"] = sum(1 for i in _inventario if i["ok"])
    out["nao_lidos"] = sum(1 for i in _inventario if not i["ok"])
    return out


def reindex() -> int:
    global _corpus_cache
    _corpus_cache = _build_corpus()
    return len(_corpus_cache)


def _retrieve(query: str, k: int = 4) -> list[dict[str, Any]]:
    qt = list(dict.fromkeys(_tokens(query)))  # únicos, preserva ordem
    if not qt:
        return []
    chunks = corpus()
    docs = [(_norm(c["text"]), _norm(c["title"] + " " + c["source"])) for c in chunks]
    n = len(chunks) or 1
    import math
    # BM25 (k1=1.5, b=0.75) em vez de contagem bruta de termos.
    #
    # Com contagem bruta, um SKILL.md de 80 kB que repete "meta", "real" e "OEE"
    # trinta vezes vencia sempre a planilha de KPIs que tem a resposta em uma
    # linha. O BM25 satura a frequencia (a 30a ocorrencia vale quase nada) e
    # normaliza pelo tamanho do trecho: um trecho curto e denso no termo ganha.
    k1, b = 1.5, 0.75
    lens = [len(bd.split()) for bd, _ in docs]
    avg = (sum(lens) / len(lens)) if lens else 1.0
    df = {t: sum(1 for bd, _ in docs if t in bd) for t in qt}
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in qt}
    scored = []
    for (body, head), c, ln in zip(docs, chunks, lens):
        score = 0.0
        for t in qt:
            tf = body.count(t)
            if tf:
                score += idf[t] * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * ln / avg))
            if t in head:
                score += 2.0 * idf[t]      # titulo/fonte: sinal forte e curto
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    # Diversidade de fontes: no maximo 2 trechos por arquivo. Com 1113 chunks de
    # skills, um unico SKILL.md longo ocupava as 4 vagas e a resposta citava tres
    # vezes o mesmo documento — o usuario perde a segunda leitura sobre o tema.
    out: list[dict[str, Any]] = []
    por_fonte: dict[str, int] = {}
    for _, c in scored:
        f = c["source"]
        if por_fonte.get(f, 0) >= 2:
            continue
        por_fonte[f] = por_fonte.get(f, 0) + 1
        out.append(c)
        if len(out) >= k:
            break
    return out


def _excerpt(text: str, query: str, n: int = 360) -> str:
    """Trecho mais relevante do chunk (janela em torno do 1º termo achado)."""
    low = _norm(text)
    for t in _tokens(query):
        i = low.find(t)
        if i >= 0:
            start = max(0, i - 80)
            return ("…" if start else "") + text[start:start + n].strip() + "…"
    return text[:n].strip() + ("…" if len(text) > n else "")


# ── Ask (RAG + grounding) ────────────────────────────────────────────
def ask(question: str) -> dict[str, Any]:
    hits = _retrieve(question, 4)
    engine = "extractive-rag"
    if not hits:
        ans = "Não encontrei nada na base de conhecimento (specs + estado do sistema) sobre isso. Reformule ou reindexe."
        cites: list[dict[str, str]] = []
    else:
        cites = [{"source": h["source"], "title": h["title"]} for h in hits[:3]]
        # síntese pelo modelo selecionado (MLX / LM Studio); fallback extrativo
        try:
            from . import providers
            syn, engine = providers.generate(question, hits)
            ans = syn or _excerpt(hits[0]["text"], question)
        except Exception:  # noqa: BLE001
            ans = _excerpt(hits[0]["text"], question)
    iid = _log(question, ans, cites)
    return {"id": iid, "answer": ans, "citations": cites, "grounded": bool(cites), "engine": engine}


def _log(question: str, answer: str, citations: list[dict[str, str]]) -> int:
    import json
    # RETURNING funciona nos dois bancos (SQLite 3.35+ e PostgreSQL);
    # `lastrowid` só existe no SQLite e devolvia 0 no Postgres — o voto do
    # flywheel ia para o id 0 e sumia.
    cur = get_connection().execute(
        "INSERT INTO ia_interaction(question,answer,citations_json,vote,ts) VALUES (?,?,?,?,?) RETURNING id",
        (question, answer, json.dumps(citations, ensure_ascii=False), None, _now()))
    row = cur.fetchone()
    return int((dict(row) if row else {}).get("id") or 0)


def feedback(interaction_id: int, vote: int) -> dict[str, Any]:
    get_connection().execute("UPDATE ia_interaction SET vote=? WHERE id=?", (1 if vote > 0 else -1, interaction_id))
    return {"ok": True}


def interactions(limit: int = 30) -> list[dict[str, Any]]:
    import json
    rows = get_connection().execute(
        "SELECT id,question,answer,citations_json,vote,ts FROM ia_interaction ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["citations"] = json.loads(d.pop("citations_json") or "[]")
        out.append(d)
    return out


# ── Eval harness (verificar ganho — pilar §7.2) ──────────────────────
def run_eval() -> dict[str, Any]:
    passed = grounded = 0
    details = []
    for q, expect in _GOLDEN:
        hits = _retrieve(q, 4)
        blob = _norm(" ".join(h["title"] + " " + h["text"] for h in hits))
        hit = expect in blob
        passed += hit
        grounded += bool(hits)
        details.append({"q": q, "expect": expect, "pass": hit})
    n = len(_GOLDEN)
    score = round(100 * passed / n, 1)
    grounding = round(100 * grounded / n, 1)
    get_connection().execute(
        "INSERT INTO ia_eval(version,score,grounding,ts) VALUES (?,?,?,?)",
        ("extractive-rag", score, grounding, _now()))
    return {"score": score, "grounding": grounding, "passed": passed, "total": n, "details": details}


def eval_history(limit: int = 10) -> list[dict[str, Any]]:
    return [dict(r) for r in get_connection().execute(
        "SELECT version,score,grounding,ts FROM ia_eval ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


# ── Agente de ganhos (insights ancorados em dado, §8) ────────────────
def insights() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from .. import audit
        s = audit.summary()
        cats = s.get("by_category", {})
        if cats:
            top = max(cats.items(), key=lambda x: x[1])
            out.append({"kind": "atividade", "text": f"Categoria mais ativa: {top[0]} ({top[1]} eventos).", "evidence": "trilha de auditoria"})
        al = s.get("alerts", 0)
        if al:
            out.append({"kind": "risco", "text": f"{al} evento(s) de alerta/NOK na trilha — revisar ocorrências.", "evidence": "audit_event severity"})
    except Exception:  # noqa: BLE001
        pass
    for tbl, lbl, col, where in [
        ("thermal_reading", "Termografia", "severity", "severity IN ('AGIR','CRITICO')"),
        ("metro_measurement", "Metrologia", "verdict", "verdict='NAO_CONFORME'"),
    ]:
        try:
            r = get_connection().execute(f"SELECT COUNT(*) AS n FROM {tbl} WHERE {where}").fetchone()
            n = dict(r)["n"]
            if n:
                out.append({"kind": "gargalo", "text": f"{lbl}: {n} caso(s) fora do padrão ({col}).", "evidence": tbl})
        except Exception:  # noqa: BLE001
            pass
    if not out:
        out.append({"kind": "ok", "text": "Sem desvios relevantes nos dados atuais. Gere atividade (eventos/medições) para insights.", "evidence": "—"})
    return out


# ── Status (fundação + Mac/MLX + flywheel) ───────────────────────────
def _apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")


def _has(mod: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(mod) is not None


def status() -> dict[str, Any]:
    conn = get_connection()

    def c(sql: str) -> int:
        try:
            return int(dict(conn.execute(sql).fetchone())["n"])
        except Exception:  # noqa: BLE001
            return 0
    vlm = False
    try:
        from ..inference.vlm.claude_client import claude_vlm
        vlm = claude_vlm.available()
    except Exception:  # noqa: BLE001
        pass
    from . import lmstudio, mlx_llm, providers
    models = providers.catalog()
    cur = next((m for m in models if m["current"]), None)
    foundation = (cur["label"] + " (soberano)") if cur else "RAG extrativo (local)"
    last_eval = eval_history(1)
    return {
        "foundation": foundation,
        "current_model": cur["id"] if cur else "extractive",
        "models": models,
        "vlm_available": vlm,
        "lmstudio_available": lmstudio.available(),
        "lmstudio_url": lmstudio.base_url(),
        "apple_silicon": _apple_silicon(),
        "mlx_available": mlx_llm.available(),
        "models_dir": mlx_llm.models_dir(),
        "frameworks": [
            {"name": "MLX", "role": "fine-tune LoRA/QLoRA local (lab) — memória unificada", "ready": _has("mlx")},
            {"name": "Foundation Models", "role": "inferência on-device leve (Swift) — app/companion", "ready": _apple_silicon()},
            {"name": "Core ML / CreateML", "role": "modelos auxiliares on-device", "ready": _apple_silicon()},
            {"name": "Vision", "role": "OCR de documento / detecção (ferramenta do agente)", "ready": _apple_silicon()},
            {"name": "Speech", "role": "transcrição on-device (entrada do agente)", "ready": _apple_silicon()},
        ],
        "knowledge_chunks": len(corpus()),
        "knowledge_by_kind": _por_kind(),
        "flywheel": {
            "interactions": c("SELECT COUNT(*) AS n FROM ia_interaction"),
            "feedback_pos": c("SELECT COUNT(*) AS n FROM ia_interaction WHERE vote=1"),
            "feedback_neg": c("SELECT COUNT(*) AS n FROM ia_interaction WHERE vote=-1"),
            "evals": c("SELECT COUNT(*) AS n FROM ia_eval"),
        },
        "last_eval": last_eval[0] if last_eval else None,
        "guardrails": ["grounding+citações", "human-in-the-loop", "só lê/recomenda (imutabilidade)", "soberania de dados (on-device)"],
    }
