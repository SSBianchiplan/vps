"""Leitor de documentos do iaMAC — transforma QUALQUER arquivo suportado em texto.

POR QUE EXISTE

O RAG lia só `.md`. Um PDF de norma, um `.docx` de procedimento ou uma planilha
de KPIs colocados na pasta simplesmente não existiam para a IA — sem aviso. Este
módulo é o único lugar que sabe abrir formatos; o motor do RAG só pede
`ler(caminho)` e recebe texto + metadados.

Cada formato degrada com honestidade: se a biblioteca (pypdf, python-docx,
openpyxl, python-pptx) não está instalada, o arquivo entra no inventário como
"não lido: instale X" em vez de sumir. O inventário é o que responde
"quais arquivos você tem?" — inclusive os que não foram lidos.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Texto puro e código: lidos como estão.
_TEXTO = {".md", ".txt", ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml", ".sql", ".log",
          ".ini", ".toml", ".cfg", ".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".ps1", ".rst", ".tex"}
_HTML = {".html", ".htm"}
_BINARIOS = {".pdf": "pypdf", ".docx": "python-docx", ".xlsx": "openpyxl", ".xlsm": "openpyxl", ".pptx": "python-pptx"}

SUPORTADOS: set[str] = set(_TEXTO) | set(_HTML) | set(_BINARIOS)
_TAMANHO_MAX = 40 * 1024 * 1024   # 40 MB: acima disso é vídeo/imagem disfarçado, não documento


def suportado(path: Path) -> bool:
    return path.suffix.lower() in SUPORTADOS


def tipo(path: Path) -> str:
    """Rótulo humano do formato, para o inventário e a interface."""
    ext = path.suffix.lower()
    return {".pdf": "PDF", ".docx": "Word", ".xlsx": "Excel", ".xlsm": "Excel", ".pptx": "PowerPoint",
            ".md": "Markdown", ".txt": "Texto", ".csv": "CSV", ".tsv": "TSV", ".json": "JSON",
            ".html": "HTML", ".htm": "HTML", ".yaml": "YAML", ".yml": "YAML", ".xml": "XML",
            ".sql": "SQL", ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript"}.get(ext, ext.lstrip(".").upper() or "?")


def _texto(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    try:
        import chardet  # type: ignore
        enc = (chardet.detect(raw[:200_000]) or {}).get("encoding") or "latin-1"
        return raw.decode(enc, errors="ignore")
    except Exception:  # noqa: BLE001
        return raw.decode("latin-1", errors="ignore")


def _html(path: Path) -> str:
    raw = _texto(path)
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(raw, "html.parser")
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        return soup.get_text("\n")
    except Exception:  # noqa: BLE001
        # sem bs4: tira tags à unha — pior que o parser, melhor que nada
        raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
        return re.sub(r"<[^>]+>", " ", raw)


def _pdf(path: Path) -> list[tuple[str, str]]:
    """[(título, texto)] por página — a citação diz a página."""
    from pypdf import PdfReader  # type: ignore
    reader = PdfReader(str(path))
    out = []
    for i, pg in enumerate(reader.pages, 1):
        try:
            t = pg.extract_text() or ""
        except Exception:  # noqa: BLE001
            t = ""
        if t.strip():
            out.append((f"página {i}", t))
    return out


def _docx(path: Path) -> str:
    import docx  # type: ignore
    d = docx.Document(str(path))
    partes = [p.text for p in d.paragraphs if p.text and p.text.strip()]
    for tb in d.tables:
        for row in tb.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                partes.append(" | ".join(cells))
    return "\n".join(partes)


def _xlsx(path: Path) -> list[tuple[str, str]]:
    """[(aba, texto)] — cada aba vira um bloco, linhas como 'a | b | c'."""
    import openpyxl  # type: ignore
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        linhas = []
        for row in ws.iter_rows(values_only=True):
            vals = ["" if v is None else str(v) for v in row]
            if any(v.strip() for v in vals):
                linhas.append(" | ".join(vals).rstrip(" |"))
            if len(linhas) >= 2000:      # planilha gigante: o RAG não precisa de 200k linhas
                linhas.append("… (aba truncada em 2000 linhas)")
                break
        if linhas:
            out.append((f"aba {ws.title}", "\n".join(linhas)))
    return out


def _pptx(path: Path) -> list[tuple[str, str]]:
    from pptx import Presentation  # type: ignore
    prs = Presentation(str(path))
    out = []
    for i, slide in enumerate(prs.slides, 1):
        textos = []
        for sh in slide.shapes:
            if getattr(sh, "has_text_frame", False) and sh.text_frame.text.strip():
                textos.append(sh.text_frame.text)
        if textos:
            out.append((f"slide {i}", "\n".join(textos)))
    return out


def ler(path: Path) -> dict[str, Any]:
    """Lê um arquivo. Devolve {"ok", "blocos": [(título, texto)], "erro", "bytes", "tipo"}.

    Nunca levanta exceção: o motor precisa continuar indexando os outros
    arquivos, e o inventário precisa saber POR QUE este ficou de fora.
    """
    meta: dict[str, Any] = {"ok": False, "blocos": [], "erro": None, "bytes": 0, "tipo": tipo(path)}
    try:
        meta["bytes"] = path.stat().st_size
    except OSError:
        pass
    ext = path.suffix.lower()
    if ext not in SUPORTADOS:
        meta["erro"] = f"formato {ext or '(sem extensão)'} não suportado"
        return meta
    if meta["bytes"] > _TAMANHO_MAX:
        meta["erro"] = f"arquivo grande demais ({meta['bytes'] // (1024 * 1024)} MB > 40 MB)"
        return meta
    try:
        if ext in _TEXTO:
            texto = _texto(path)
            if ext == ".json":
                # JSON reindentado lê melhor que uma linha de 80 kB
                try:
                    texto = json.dumps(json.loads(texto), ensure_ascii=False, indent=1)
                except Exception:  # noqa: BLE001
                    pass
            meta["blocos"] = [(path.stem, texto)]
        elif ext in _HTML:
            meta["blocos"] = [(path.stem, _html(path))]
        elif ext == ".pdf":
            meta["blocos"] = _pdf(path)
        elif ext == ".docx":
            meta["blocos"] = [(path.stem, _docx(path))]
        elif ext in (".xlsx", ".xlsm"):
            meta["blocos"] = _xlsx(path)
        elif ext == ".pptx":
            meta["blocos"] = _pptx(path)
        meta["ok"] = True
        if not any(t.strip() for _, t in meta["blocos"]):
            meta["ok"] = False
            meta["erro"] = "sem texto extraível (imagem escaneada? use OCR antes)"
    except ImportError as e:
        lib = _BINARIOS.get(ext, str(e))
        meta["erro"] = f"não lido: instale {lib}"
    except Exception as e:  # noqa: BLE001
        meta["erro"] = f"falha ao ler: {type(e).__name__}: {str(e)[:80]}"
    return meta


def em_pedacos(texto: str, alvo: int = 1400) -> list[str]:
    """Quebra texto longo em pedaços de ~alvo caracteres, por parágrafo.

    Um chunk de 80 kB afoga a recuperação: o IDF acha o termo, mas o trecho
    devolvido é um bloco ilegível. Pedaços de ~1400 caracteres cabem numa
    citação e mantêm o parágrafo inteiro.
    """
    paras = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    out: list[str] = []
    buf = ""
    for p in paras:
        if len(p) > alvo * 2:       # parágrafo gigante (planilha, log): corta por linhas
            for i in range(0, len(p), alvo):
                out.append(p[i:i + alvo])
            continue
        if len(buf) + len(p) + 1 > alvo and buf:
            out.append(buf)
            buf = p
        else:
            buf = f"{buf}\n{p}" if buf else p
    if buf:
        out.append(buf)
    return out
