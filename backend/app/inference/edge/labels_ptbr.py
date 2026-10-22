"""Tradução PT-BR das classes COCO (YOLO) e sinônimos PT→COCO.

Usado pelos caminhos edge de DESCREVER (texto em PT) e ANALISAR (interpretar
critérios escritos em português → classe COCO). Cobre as 80 classes COCO; chaves
extras mapeiam variações comuns de digitação do operador.
"""
from __future__ import annotations

# COCO (en) → PT-BR (singular, plural)
COCO_PTBR: dict[str, tuple[str, str]] = {
    "person": ("pessoa", "pessoas"),
    "bicycle": ("bicicleta", "bicicletas"),
    "car": ("carro", "carros"),
    "motorcycle": ("moto", "motos"),
    "airplane": ("avião", "aviões"),
    "bus": ("ônibus", "ônibus"),
    "train": ("trem", "trens"),
    "truck": ("caminhão", "caminhões"),
    "boat": ("barco", "barcos"),
    "traffic light": ("semáforo", "semáforos"),
    "fire hydrant": ("hidrante", "hidrantes"),
    "stop sign": ("placa de pare", "placas de pare"),
    "parking meter": ("parquímetro", "parquímetros"),
    "bench": ("banco", "bancos"),
    "bird": ("pássaro", "pássaros"),
    "cat": ("gato", "gatos"),
    "dog": ("cachorro", "cachorros"),
    "horse": ("cavalo", "cavalos"),
    "sheep": ("ovelha", "ovelhas"),
    "cow": ("vaca", "vacas"),
    "elephant": ("elefante", "elefantes"),
    "bear": ("urso", "ursos"),
    "zebra": ("zebra", "zebras"),
    "giraffe": ("girafa", "girafas"),
    "backpack": ("mochila", "mochilas"),
    "umbrella": ("guarda-chuva", "guarda-chuvas"),
    "handbag": ("bolsa", "bolsas"),
    "tie": ("gravata", "gravatas"),
    "suitcase": ("mala", "malas"),
    "frisbee": ("frisbee", "frisbees"),
    "skis": ("esqui", "esquis"),
    "snowboard": ("snowboard", "snowboards"),
    "sports ball": ("bola", "bolas"),
    "kite": ("pipa", "pipas"),
    "baseball bat": ("taco de beisebol", "tacos de beisebol"),
    "baseball glove": ("luva de beisebol", "luvas de beisebol"),
    "skateboard": ("skate", "skates"),
    "surfboard": ("prancha de surfe", "pranchas de surfe"),
    "tennis racket": ("raquete", "raquetes"),
    "bottle": ("garrafa", "garrafas"),
    "wine glass": ("taça", "taças"),
    "cup": ("copo", "copos"),
    "fork": ("garfo", "garfos"),
    "knife": ("faca", "facas"),
    "spoon": ("colher", "colheres"),
    "bowl": ("tigela", "tigelas"),
    "banana": ("banana", "bananas"),
    "apple": ("maçã", "maçãs"),
    "sandwich": ("sanduíche", "sanduíches"),
    "orange": ("laranja", "laranjas"),
    "broccoli": ("brócolis", "brócolis"),
    "carrot": ("cenoura", "cenouras"),
    "hot dog": ("cachorro-quente", "cachorros-quentes"),
    "pizza": ("pizza", "pizzas"),
    "donut": ("rosquinha", "rosquinhas"),
    "cake": ("bolo", "bolos"),
    "chair": ("cadeira", "cadeiras"),
    "couch": ("sofá", "sofás"),
    "potted plant": ("planta", "plantas"),
    "bed": ("cama", "camas"),
    "dining table": ("mesa", "mesas"),
    "toilet": ("vaso sanitário", "vasos sanitários"),
    "tv": ("televisão", "televisões"),
    "laptop": ("notebook", "notebooks"),
    "mouse": ("mouse", "mouses"),
    "remote": ("controle remoto", "controles remotos"),
    "keyboard": ("teclado", "teclados"),
    "cell phone": ("celular", "celulares"),
    "microwave": ("micro-ondas", "micro-ondas"),
    "oven": ("forno", "fornos"),
    "toaster": ("torradeira", "torradeiras"),
    "sink": ("pia", "pias"),
    "refrigerator": ("geladeira", "geladeiras"),
    "book": ("livro", "livros"),
    "clock": ("relógio", "relógios"),
    "vase": ("vaso", "vasos"),
    "scissors": ("tesoura", "tesouras"),
    "teddy bear": ("urso de pelúcia", "ursos de pelúcia"),
    "hair drier": ("secador", "secadores"),
    "toothbrush": ("escova de dentes", "escovas de dentes"),
}

# Classes que, presentes em cena de segurança, merecem destaque como alerta.
ALERT_CLASSES = {"person", "car", "truck", "motorcycle", "bus", "bicycle", "dog", "cat", "knife"}


def ptbr(classe: str, plural: bool = False) -> str:
    """Nome PT-BR (singular/plural) da classe; fallback = própria string.

    Cobre as 80 COCO aqui e, para o vocabulário maior (Objects365, 365 classes),
    cai no catálogo de classes-alvo. Sem esse segundo passo a descrição no motor
    local sairia meio em português e meio em inglês — "3 pessoas e 2 sneakers".
    """
    par = COCO_PTBR.get(classe)
    if par is not None:
        return par[1] if plural else par[0]
    from .target_classes import TARGET_150
    alvo = TARGET_150.get(classe)
    return alvo[0] if alvo else classe


def _build_pt_index() -> dict[str, str]:
    """Índice PT-BR (e variações) → classe COCO, para interpretar critérios."""
    idx: dict[str, str] = {}
    for en, (sing, plur) in COCO_PTBR.items():
        idx[en] = en
        idx[sing] = en
        idx[plur] = en
    # Vocabulário estendido: o operador escreve "capacete" ou "extintor" no
    # critério de ANALISAR e isso precisa achar a classe do modelo.
    from .target_classes import TARGET_150
    for en, (pt, _grupo) in TARGET_150.items():
        idx.setdefault(en, en)
        idx.setdefault(pt, en)
    # sinônimos/variações comuns do operador
    extra = {
        "pessoa": "person", "pessoas": "person", "gente": "person", "homem": "person",
        "mulher": "person", "individuo": "person", "indivíduo": "person", "humano": "person",
        "veiculo": "car", "veículo": "car", "automovel": "car", "automóvel": "car", "auto": "car",
        "caminhao": "truck", "onibus": "bus", "motocicleta": "motorcycle",
        "cao": "dog", "cão": "dog", "cachorro": "dog", "celular": "cell phone",
        "telefone": "cell phone", "garrafa": "bottle",
        # "caixa" era mapeado para suitcase (mala). Com o vocabulario Objects365
        # existe a classe certa; mala continua alcancavel por "mala".
        "caixa": "storage box", "caixas": "storage box", "contentor": "storage box",
        # APROXIMACOES conscientes do vocabulario industrial: o modelo nao tem
        # classe propria para estes itens, e detecta o mais proximo. Melhor um
        # alvo aproximado e declarado aqui do que o operador digitar e nao ter
        # deteccao nenhuma sem nunca saber por que.
        "empilhadeira": "machinery vehicle", "retroescavadeira": "machinery vehicle",
        "trator": "machinery vehicle", "maquina": "machinery vehicle",
        "epi": "helmet", "capacete de seguranca": "helmet",
        "extintor de incendio": "fire extinguisher",
        "cone": "traffic cone", "cavalete": "traffic cone",
    }
    idx.update(extra)
    return idx


PT_TO_COCO = _build_pt_index()


def resolve_class(term: str) -> str | None:
    """Resolve um termo livre (PT/EN) para classe COCO, ou None se não reconhecido."""
    t = term.strip().lower()
    if not t:
        return None
    if t in PT_TO_COCO:
        return PT_TO_COCO[t]
    # tenta casar por substring (ex.: "uma pessoa na cena" contém "pessoa")
    for key, coco in PT_TO_COCO.items():
        if len(key) >= 4 and key in t:
            return coco
    return None
