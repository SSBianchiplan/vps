"""Catálogo de classes-alvo — 150 classes operacionais, em PT-BR.

POR QUE ESTE ARQUIVO EXISTE

O campo "Classes-alvo" era texto livre. Quem não soubesse o nome exato que o
modelo usa digitava "empilhadeira" ou "capacete" e a regra simplesmente nunca
disparava: sem erro, sem aviso, só um alarme que não toca. Este catálogo é a
lista fechada do que o detector REALMENTE reconhece, com o nome em português.

O vocabulário vem do modelo carregado (`/api/infer/classes` cruza esta lista com
`model.names`), então uma classe que o modelo não conhece nunca é oferecida —
é a mesma disciplina de whitelist usada nos operadores de visão.

As 150 saem do vocabulário Objects365 (365 classes) do `yolo26s-objv1-150`.
Com o modelo COCO (80 classes) a interface oferece apenas a interseção, sem
quebrar: o cruzamento é feito em tempo de execução.
"""
from __future__ import annotations

# nome no modelo → (PT-BR, grupo)
TARGET_150: dict[str, tuple[str, str]] = {
    # ── Pessoas e EPI (14) ───────────────────────────────────────────
    "person": ("pessoa", "Pessoas e EPI"),
    "hat": ("boné/chapéu", "Pessoas e EPI"),
    "helmet": ("capacete", "Pessoas e EPI"),
    "glove": ("luva", "Pessoas e EPI"),
    "glasses": ("óculos", "Pessoas e EPI"),
    "boots": ("bota", "Pessoas e EPI"),
    "leather shoes": ("sapato", "Pessoas e EPI"),
    "sneakers": ("tênis", "Pessoas e EPI"),
    "facial mask": ("máscara facial", "Pessoas e EPI"),
    "tie": ("gravata", "Pessoas e EPI"),
    "belt": ("cinto", "Pessoas e EPI"),
    "backpack": ("mochila", "Pessoas e EPI"),
    "handbag": ("bolsa", "Pessoas e EPI"),
    "watch": ("relógio de pulso", "Pessoas e EPI"),
    # ── Veículos e movimentação (26) ─────────────────────────────────
    "car": ("carro", "Veículos"),
    "suv": ("utilitário (SUV)", "Veículos"),
    "van": ("van", "Veículos"),
    "truck": ("caminhão", "Veículos"),
    "pickup truck": ("caminhonete", "Veículos"),
    "bus": ("ônibus", "Veículos"),
    "motorcycle": ("moto", "Veículos"),
    "bicycle": ("bicicleta", "Veículos"),
    "tricycle": ("triciclo", "Veículos"),
    "machinery vehicle": ("máquina/veículo industrial", "Veículos"),
    "fire truck": ("caminhão de bombeiros", "Veículos"),
    "ambulance": ("ambulância", "Veículos"),
    "crane": ("guindaste", "Veículos"),
    "train": ("trem", "Veículos"),
    "sports car": ("carro esportivo", "Veículos"),
    "race car": ("carro de corrida", "Veículos"),
    "rickshaw": ("carrinho de tração", "Veículos"),
    "trolley": ("carrinho de carga", "Veículos"),
    "stroller": ("carrinho de bebê", "Veículos"),
    "wheelchair": ("cadeira de rodas", "Veículos"),
    "skateboard": ("skate", "Veículos"),
    "airplane": ("avião", "Veículos"),
    "helicopter": ("helicóptero", "Veículos"),
    "boat": ("barco", "Veículos"),
    "sailboat": ("veleiro", "Veículos"),
    "ship": ("navio", "Veículos"),
    # ── Logística e armazém (12) ─────────────────────────────────────
    "barrel/bucket": ("tambor/balde", "Logística"),
    "storage box": ("caixa/contentor", "Logística"),
    "basket": ("cesto", "Logística"),
    "luggage": ("bagagem", "Logística"),
    "suitcase": ("mala", "Logística"),
    "ladder": ("escada", "Logística"),
    "tent": ("tenda", "Logística"),
    "computer box": ("gabinete/caixa", "Logística"),
    "bottle": ("garrafa", "Logística"),
    "cup": ("copo", "Logística"),
    "plate": ("prato", "Logística"),
    "bowl": ("tigela", "Logística"),
    # ── Ferramentas e manutenção (22) ────────────────────────────────
    "hammer": ("martelo", "Ferramentas"),
    "screwdriver": ("chave de fenda", "Ferramentas"),
    "pliers": ("alicate", "Ferramentas"),
    "saw": ("serra", "Ferramentas"),
    "chainsaw": ("motosserra", "Ferramentas"),
    "electric drill": ("furadeira", "Ferramentas"),
    "shovel": ("pá", "Ferramentas"),
    "tape measure/ruler": ("trena/régua", "Ferramentas"),
    "scale": ("balança", "Ferramentas"),
    "paint brush": ("pincel", "Ferramentas"),
    "brush": ("escova", "Ferramentas"),
    "broom": ("vassoura", "Ferramentas"),
    "mop": ("rodo/esfregão", "Ferramentas"),
    "tong": ("pinça/tenaz", "Ferramentas"),
    "marker": ("marcador", "Ferramentas"),
    "pen/pencil": ("caneta/lápis", "Ferramentas"),
    "scissors": ("tesoura", "Ferramentas"),
    "knife": ("faca", "Ferramentas"),
    "key": ("chave", "Ferramentas"),
    "lighter": ("isqueiro", "Ferramentas"),
    "iron": ("ferro", "Ferramentas"),
    "flashlight": ("lanterna", "Ferramentas"),
    # ── Elétrica e utilidades (19) ───────────────────────────────────
    "power outlet": ("tomada", "Elétrica e utilidades"),
    "extension cord": ("extensão elétrica", "Elétrica e utilidades"),
    "converter": ("conversor/fonte", "Elétrica e utilidades"),
    "router/modem": ("roteador/modem", "Elétrica e utilidades"),
    "radiator": ("radiador", "Elétrica e utilidades"),
    "fan": ("ventilador", "Elétrica e utilidades"),
    "air conditioner": ("ar-condicionado", "Elétrica e utilidades"),
    "vent": ("grelha de ventilação", "Elétrica e utilidades"),
    "gas stove": ("fogão", "Elétrica e utilidades"),
    "washing machine": ("máquina de lavar", "Elétrica e utilidades"),
    "refrigerator": ("refrigerador", "Elétrica e utilidades"),
    "oven": ("forno", "Elétrica e utilidades"),
    "microwave": ("micro-ondas", "Elétrica e utilidades"),
    "coffee machine": ("cafeteira", "Elétrica e utilidades"),
    "blender": ("liquidificador", "Elétrica e utilidades"),
    "kettle": ("chaleira", "Elétrica e utilidades"),
    "toaster": ("torradeira", "Elétrica e utilidades"),
    "rice cooker": ("panela elétrica", "Elétrica e utilidades"),
    "treadmill": ("esteira", "Elétrica e utilidades"),
    # ── Segurança e sinalização (13) ─────────────────────────────────
    "fire hydrant": ("hidrante", "Segurança"),
    "fire extinguisher": ("extintor", "Segurança"),
    "surveillance camera": ("câmera de vigilância", "Segurança"),
    "traffic cone": ("cone de sinalização", "Segurança"),
    "traffic sign": ("placa de trânsito", "Segurança"),
    "traffic light": ("semáforo", "Segurança"),
    "stop sign": ("placa PARE", "Segurança"),
    "crosswalk sign": ("placa de faixa de pedestre", "Segurança"),
    "parking meter": ("parquímetro", "Segurança"),
    "gun": ("arma de fogo", "Segurança"),
    "life saver": ("boia salva-vidas", "Segurança"),
    "hurdle": ("barreira", "Segurança"),
    "target": ("alvo", "Segurança"),
    # ── TI e escritório (18) ─────────────────────────────────────────
    "laptop": ("notebook", "TI e escritório"),
    "tablet": ("tablet", "TI e escritório"),
    "keyboard": ("teclado", "TI e escritório"),
    "mouse": ("mouse", "TI e escritório"),
    "tv": ("monitor/TV", "TI e escritório"),
    "cell phone": ("celular", "TI e escritório"),
    "telephone": ("telefone", "TI e escritório"),
    "camera": ("câmera", "TI e escritório"),
    "printer": ("impressora", "TI e escritório"),
    "projector": ("projetor", "TI e escritório"),
    "microphone": ("microfone", "TI e escritório"),
    "speaker": ("caixa de som", "TI e escritório"),
    "head phone": ("fone de ouvido", "TI e escritório"),
    "clock": ("relógio de parede", "TI e escritório"),
    "book": ("livro", "TI e escritório"),
    "calculator": ("calculadora", "TI e escritório"),
    "blackboard/whiteboard": ("quadro", "TI e escritório"),
    "tripod": ("tripé", "TI e escritório"),
    # ── Ambiente e mobiliário (16) ───────────────────────────────────
    "chair": ("cadeira", "Ambiente"),
    "desk": ("mesa de trabalho", "Ambiente"),
    "dining table": ("mesa", "Ambiente"),
    "bench": ("banco", "Ambiente"),
    "couch": ("sofá", "Ambiente"),
    "bed": ("cama", "Ambiente"),
    "cabinet/shelf": ("armário/prateleira", "Ambiente"),
    "lamp": ("luminária", "Ambiente"),
    "lantern": ("lampião", "Ambiente"),
    "street lights": ("poste de iluminação", "Ambiente"),
    "sink": ("pia", "Ambiente"),
    "faucet": ("torneira", "Ambiente"),
    "toilet": ("vaso sanitário", "Ambiente"),
    "trash bin/can": ("lixeira", "Ambiente"),
    "potted plant": ("planta em vaso", "Ambiente"),
    "umbrella": ("guarda-chuva", "Ambiente"),
    # ── Animais (perímetro) (10) ─────────────────────────────────────
    "dog": ("cachorro", "Animais"),
    "cat": ("gato", "Animais"),
    "wild bird": ("ave", "Animais"),
    "pigeon": ("pombo", "Animais"),
    "horse": ("cavalo", "Animais"),
    "cow": ("vaca", "Animais"),
    "sheep": ("ovelha", "Animais"),
    "chicken": ("galinha", "Animais"),
    "duck": ("pato", "Animais"),
    "goose": ("ganso", "Animais"),
}

# Ordem estável dos grupos na interface (do mais ao menos operacional).
GRUPOS: list[str] = [
    "Pessoas e EPI", "Veículos", "Logística", "Ferramentas",
    "Elétrica e utilidades", "Segurança", "TI e escritório", "Ambiente", "Animais",
]


def catalogo(model_names: dict[int, str] | None = None) -> list[dict[str, str]]:
    """As 150 classes, cruzadas com o vocabulário do modelo carregado.

    Sem `model_names` devolve o catálogo inteiro. Com ele, devolve só o que o
    modelo reconhece — oferecer uma classe que o modelo não tem é prometer um
    alarme que nunca dispara.
    """
    conhecidas = set(model_names.values()) if model_names else None
    out: list[dict[str, str]] = []
    for nome, (pt, grupo) in TARGET_150.items():
        if conhecidas is not None and nome not in conhecidas:
            continue
        out.append({"name": nome, "pt": pt, "grupo": grupo})
    ordem = {g: i for i, g in enumerate(GRUPOS)}
    out.sort(key=lambda c: (ordem.get(c["grupo"], 99), c["pt"]))
    return out


def pt_de(nome: str) -> str:
    """Rótulo PT de uma classe; o próprio nome quando não catalogada."""
    v = TARGET_150.get(nome)
    return v[0] if v else nome
