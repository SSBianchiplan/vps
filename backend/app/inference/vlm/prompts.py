"""Prompts e JSON Schemas (subconjunto suportado) para cada modo do VLM.

Os schemas usam apenas object/array/string/number/integer/boolean/enum com
`additionalProperties: false` + `required` — o subconjunto aceito por
output_config.format (structured outputs). Mapas de chave dinâmica (contagens)
são modelados como arrays de {classe, quantidade}.
"""
from __future__ import annotations

from ...schemas.tasks import AnalyzeParams, CountParams, DescribeParams, ReadParams

# ── DESCREVER ───────────────────────────────────────────────────────
DESCRIBE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "descricao": {"type": "string"},
        "objetos": {"type": "array", "items": {"type": "string"}},
        "alertas": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["descricao", "objetos", "alertas"],
}


def describe_prompt(params: DescribeParams, prompt: str | None) -> str:
    foco = params.foco or prompt or "a cena como um todo"
    return (
        "Você é um assistente de visão computacional. Descreva objetivamente o "
        "que aparece na imagem.\n"
        f"Foco: {foco}\n"
        f"Nível de detalhe: {params.nivel_detalhe}.\n"
        "Liste os objetos relevantes e quaisquer alertas (anomalias, riscos, "
        "itens fora do lugar). Responda no formato JSON solicitado."
    )


# ── ANALISAR ────────────────────────────────────────────────────────
ANALYZE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "veredito": {"type": "string", "enum": ["OK", "NOK"]},
        "confianca": {"type": "number"},
        "itens_verificados": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "criterio": {"type": "string"},
                    "atende": {"type": "boolean"},
                    "observacao": {"type": "string"},
                },
                "required": ["criterio", "atende", "observacao"],
            },
        },
        "resumo": {"type": "string"},
    },
    "required": ["veredito", "confianca", "itens_verificados", "resumo"],
}


def analyze_prompt(params: AnalyzeParams, prompt: str | None) -> str:
    criterios = "\n".join(f"- {c}" for c in params.criterios) or "- (avaliação geral de conformidade)"
    extra = f"\nInstrução adicional do operador: {prompt}" if prompt else ""
    rubrica = f"\nRubrica: {params.rubrica}" if params.rubrica else ""
    return (
        "Você é um inspetor de qualidade industrial. Analise a imagem segundo os "
        "critérios abaixo e emita um veredito.\n"
        f"Critérios:\n{criterios}{rubrica}{extra}\n\n"
        "Use 'OK' quando todos os critérios essenciais forem atendidos e 'NOK' "
        "caso contrário. Para cada critério informe se atende e uma observação "
        "curta. 'confianca' é sua confiança no veredito entre 0.0 e 1.0. "
        "Responda no formato JSON solicitado."
    )


# ── LER ─────────────────────────────────────────────────────────────
READ_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "leituras": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "texto": {"type": "string"},
                    "campo": {"type": "string"},
                    "confianca": {"type": "number"},
                    "bbox": {"type": "array", "items": {"type": "number"}},
                },
                "required": ["texto", "campo", "confianca", "bbox"],
            },
        }
    },
    "required": ["leituras"],
}


def read_prompt(params: ReadParams, prompt: str | None) -> str:
    campos = ", ".join(params.campos_logicos) if params.campos_logicos else "nenhum específico"
    padrao = f"\nPadrão esperado (regex de referência): {params.pattern_regex}" if params.pattern_regex else ""
    extra = f"\nInstrução adicional: {prompt}" if prompt else ""
    return (
        "Você é um sistema de OCR estruturado. Extraia todo o texto/códigos/"
        "números relevantes da imagem.\n"
        f"Idioma principal: {params.idioma}.\n"
        f"Campos lógicos a mapear (se identificáveis): {campos}.{padrao}{extra}\n\n"
        "Para cada leitura informe: 'texto' (string reconhecida), 'campo' (o "
        "campo lógico correspondente ou string vazia se não se aplicar), "
        "'confianca' (0.0 a 1.0) e 'bbox' como [x, y, w, h] em coordenadas "
        "normalizadas de 0 a 1 relativas à imagem. Responda no formato JSON."
    )


# ── CONTAR (fallback por snapshot, sem edge) ────────────────────────
COUNT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "itens": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "classe": {"type": "string"},
                    "quantidade": {"type": "integer"},
                },
                "required": ["classe", "quantidade"],
            },
        },
        "total": {"type": "integer"},
    },
    "required": ["itens", "total"],
}


DETECT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "objetos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "classe": {"type": "string"},
                    "confianca": {"type": "number"},
                    "bbox": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "[x,y,w,h] normalizado 0..1",
                    },
                },
                "required": ["classe", "confianca", "bbox"],
            },
        }
    },
    "required": ["objetos"],
}


def detect_prompt(classes_alvo: list[str], prompt: str | None) -> str:
    alvo = ", ".join(classes_alvo) if classes_alvo else "todos os objetos/pessoas relevantes"
    extra = f"\nInstrução adicional: {prompt}" if prompt else ""
    return (
        "Você é um detector de objetos por visão. Localize cada objeto na imagem.\n"
        f"Classes-alvo: {alvo}.{extra}\n\n"
        "Para cada objeto retorne 'classe', 'confianca' (0..1) e 'bbox' como "
        "[x, y, largura, altura] NORMALIZADO (0..1) em relação à imagem, onde (x,y) "
        "é o canto superior-esquerdo. Detecte apenas o claramente visível. JSON."
    )


def count_prompt(params: CountParams, prompt: str | None) -> str:
    classes = ", ".join(params.classes_alvo) if params.classes_alvo else "todos os objetos/pessoas relevantes"
    extra = f"\nInstrução adicional: {prompt}" if prompt else ""
    return (
        "Você é um sistema de contagem por visão. Conte os objetos na imagem.\n"
        f"Classes-alvo: {classes}.{extra}\n\n"
        "Para cada classe contada informe 'classe' e 'quantidade' (inteiro) e "
        "calcule o 'total'. Conte apenas o que estiver claramente visível. "
        "Responda no formato JSON."
    )
