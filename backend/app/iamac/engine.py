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
def _build_corpus() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for md in sorted(_ROOT.glob("*.md")):
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        title, buf, heading = md.stem, [], md.stem
        for line in text.splitlines():
            if line.startswith("## "):
                if buf:
                    chunks.append({"source": md.name, "title": heading, "text": "\n".join(buf).strip()})
                heading = line.lstrip("# ").strip(); buf = []
            elif line.startswith("# ") and title == md.stem:
                title = line.lstrip("# ").strip()
            else:
                buf.append(line)
        if buf:
            chunks.append({"source": md.name, "title": heading, "text": "\n".join(buf).strip()})
    chunks.append(_system_snapshot())
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
    return {"source": "Estado do Sistema (ao vivo)", "title": "Snapshot", "text": "\n".join(lines)}


def corpus() -> list[dict[str, Any]]:
    global _corpus_cache
    if _corpus_cache is None:
        _corpus_cache = _build_corpus()
    # snapshot ao vivo sempre atualizado (substitui o último)
    out = [c for c in _corpus_cache if c["source"] != "Estado do Sistema (ao vivo)"]
    return out + [_system_snapshot()]


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
    # IDF: termo raro (ex.: "termografia") pesa muito mais que comum ("como", "sistema")
    import math
    idf = {t: math.log(n / (1 + sum(1 for b, _ in docs if t in b))) + 0.1 for t in qt}
    scored = []
    for (body, head), c in zip(docs, chunks):
        score = sum(body.count(t) * idf[t] for t in qt) + 4 * sum((t in head) * idf[t] for t in qt)
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]


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
    cur = get_connection().execute(
        "INSERT INTO ia_interaction(question,answer,citations_json,vote,ts) VALUES (?,?,?,?,?)",
        (question, answer, json.dumps(citations, ensure_ascii=False), None, _now()))
    return int(cur.lastrowid or 0)


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
        "flywheel": {
            "interactions": c("SELECT COUNT(*) AS n FROM ia_interaction"),
            "feedback_pos": c("SELECT COUNT(*) AS n FROM ia_interaction WHERE vote=1"),
            "feedback_neg": c("SELECT COUNT(*) AS n FROM ia_interaction WHERE vote=-1"),
            "evals": c("SELECT COUNT(*) AS n FROM ia_eval"),
        },
        "last_eval": last_eval[0] if last_eval else None,
        "guardrails": ["grounding+citações", "human-in-the-loop", "só lê/recomenda (imutabilidade)", "soberania de dados (on-device)"],
    }
