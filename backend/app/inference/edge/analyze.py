"""ANALISAR no caminho edge — veredito OK/NOK por regras determinísticas sobre
as detecções YOLO, sem VLM/token.

Cada critério escrito pelo operador é interpretado por um mini-parser:
  - "pessoa"                       → presença (contagem >= 1)
  - "sem pessoa" / "nenhuma caixa" → ausência (contagem == 0)
  - "pessoa >= 2" / "carros < 5"   → comparação de contagem
  - "pelo menos 3 pessoas"         → contagem >= 3
Critérios que não casam com nenhuma classe COCO são marcados como não
verificáveis localmente (não derrubam o veredito) e sinalizados em warnings.
"""
from __future__ import annotations

import re
from collections import Counter

from ...schemas.results import AnalyzeResult, Detection, ItemVerificado
from .labels_ptbr import ptbr, resolve_class

_NEG = ("sem ", "nenhum", "nenhuma", "ausente", "ausência", "ausencia", "não ", "nao ", "zero ")
_OPS = {
    ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b, "<": lambda a, b: a < b, "=": lambda a, b: a == b,
}
_OP_RE = re.compile(r"(>=|<=|==|!=|>|<|=)\s*(\d+)")
_NUM_RE = re.compile(r"\b(\d+)\b")
_PELO_MENOS = re.compile(r"(pelo menos|no m[ií]nimo|m[ií]nimo de|>=?)\s*(\d+)")
_NO_MAX = re.compile(r"(no m[áa]ximo|m[áa]ximo de|at[ée])\s*(\d+)")
_EXATO = re.compile(r"(exatamente|igual a)\s*(\d+)")


def _evaluate(criterio: str, counts: Counter) -> ItemVerificado | None:
    """Avalia um critério; retorna None se não for verificável localmente."""
    txt = criterio.strip().lower()
    if not txt:
        return None
    coco = resolve_class(txt)
    if coco is None:
        return None  # nenhuma classe COCO reconhecida → não verificável local

    n = int(counts.get(coco, 0))
    nome = ptbr(coco, plural=True)

    # operador explícito: "pessoa >= 2"
    m = _OP_RE.search(txt)
    if m:
        op, alvo = m.group(1), int(m.group(2))
        ok = _OPS[op](n, alvo)
        return ItemVerificado(criterio=criterio, atende=ok,
                              observacao=f"{n} {nome} (esperado {op} {alvo})")

    # frases PT de quantidade
    for rx, op in ((_PELO_MENOS, ">="), (_NO_MAX, "<="), (_EXATO, "==")):
        mm = rx.search(txt)
        if mm:
            alvo = int(mm.group(2))
            ok = _OPS[op](n, alvo)
            return ItemVerificado(criterio=criterio, atende=ok,
                                  observacao=f"{n} {nome} (esperado {op} {alvo})")

    # negação → ausência esperada (contagem == 0)
    if any(neg in txt for neg in _NEG):
        ok = n == 0
        return ItemVerificado(criterio=criterio, atende=ok,
                              observacao=f"{n} {nome} (esperado: ausente)")

    # número solto sem operador: "3 pessoas" → exatamente
    mn = _NUM_RE.search(txt)
    if mn:
        alvo = int(mn.group(1))
        ok = n == alvo
        return ItemVerificado(criterio=criterio, atende=ok,
                              observacao=f"{n} {nome} (esperado {alvo})")

    # padrão: presença esperada (contagem >= 1)
    ok = n >= 1
    return ItemVerificado(criterio=criterio, atende=ok,
                          observacao=f"{n} {nome} detectada(s)" if ok else f"{nome} não detectada(s)")


def edge_analyze(
    detections: list[Detection],
    criterios: list[str],
    rotulo_ok: str = "OK",
    rotulo_nok: str = "NOK",
) -> tuple[AnalyzeResult, list[str]]:
    """Retorna (AnalyzeResult, warnings). Veredito = todos os critérios
    verificáveis atendidos."""
    counts = Counter(d.classe for d in detections)
    itens: list[ItemVerificado] = []
    nao_verificaveis = 0

    for c in criterios:
        item = _evaluate(c, counts)
        if item is None:
            nao_verificaveis += 1
            itens.append(ItemVerificado(
                criterio=c, atende=True,
                observacao="não verificável localmente (requer IA/VLM)",
            ))
        else:
            itens.append(item)

    verificaveis = [it for it in itens if not it.observacao.startswith("não verificável")]
    aprovado = all(it.atende for it in verificaveis) if verificaveis else True
    canon_ok = aprovado
    veredito = rotulo_ok if canon_ok else rotulo_nok

    if verificaveis:
        reprovados = [it.criterio for it in verificaveis if not it.atende]
        resumo = ("Todos os critérios verificáveis foram atendidos."
                  if canon_ok else f"Reprovado em: {'; '.join(reprovados)}.")
        confianca = (sum(d.confianca for d in detections) / len(detections)) if detections else 0.6
    else:
        resumo = "Nenhum critério verificável localmente — avaliação local limitada (use o motor IA)."
        confianca = 0.3

    warnings: list[str] = []
    if nao_verificaveis:
        warnings.append(f"criterios_nao_verificaveis_local={nao_verificaveis}")

    return AnalyzeResult(
        veredito=veredito,
        confianca=round(confianca, 4),
        itens_verificados=itens,
        resumo=resumo,
    ), warnings
