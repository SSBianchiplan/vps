"""DESCREVER no caminho edge — descrição PT-BR sintetizada a partir das
detecções YOLO, sem depender de VLM/token.

Não substitui a riqueza do VLM, mas entrega uma descrição objetiva e útil
(o que há na cena + contagens + alertas) totalmente local e gratuita.
"""
from __future__ import annotations

from collections import Counter

from ...schemas.results import Detection, DescribeResult
from .labels_ptbr import ALERT_CLASSES, ptbr


def _quantia(n: int, classe: str) -> str:
    nome = ptbr(classe, plural=n != 1)
    return f"{n} {nome}"


def _listar(itens: list[str]) -> str:
    """Junta em PT: 'a', 'a e b', 'a, b e c'."""
    if not itens:
        return ""
    if len(itens) == 1:
        return itens[0]
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def edge_describe(detections: list[Detection], nivel_detalhe: str = "medio") -> DescribeResult:
    """Constrói uma DescribeResult a partir das detecções do YOLO."""
    if not detections:
        return DescribeResult(
            descricao="Nenhum objeto reconhecível detectado na cena.",
            objetos=[],
            alertas=[],
        )

    counts = Counter(d.classe for d in detections)
    ordenado = counts.most_common()
    objetos = [_quantia(n, c) for c, n in ordenado]

    principais = _listar(objetos if nivel_detalhe == "alto" else objetos[:5])
    total = sum(counts.values())
    descricao = f"Cena com {total} objeto(s) detectado(s): {principais}."

    if nivel_detalhe != "baixo":
        conf_media = sum(d.confianca for d in detections) / len(detections)
        descricao += f" Confiança média da detecção: {conf_media:.0%}."

    alertas: list[str] = []
    for classe, n in ordenado:
        if classe in ALERT_CLASSES:
            alertas.append(f"{_quantia(n, classe)} em cena")

    return DescribeResult(descricao=descricao, objetos=objetos, alertas=alertas)
