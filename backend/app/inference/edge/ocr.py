"""OCR edge com degradação graciosa e múltiplos backends.

Backends, em ordem de preferência:
  1. Apple Vision (VNRecognizeTextRequest) via pyobjc — nativo no macOS, baixa
     latência, sem download de modelo. Caminho padrão neste sistema (Mac).
  2. PaddleOCR — multiplataforma (instale via requirements-edge).

Se nenhum estiver disponível, `available()` retorna False e o orquestrador usa
o VLM para LER (e, sem token, LER fica indisponível com erro claro).
"""
from __future__ import annotations

import io
from functools import lru_cache
from typing import Any

from ...schemas.results import Leitura
from ..errors import EdgeUnavailableError


# ── Backend 1: Apple Vision (macOS) ─────────────────────────────────
@lru_cache(maxsize=1)
def _vision() -> Any | None:
    try:
        import Quartz  # noqa: F401
        import Vision
        from Foundation import NSData  # noqa: F401
        return Vision
    except Exception:
        return None


def _cgimage(data: bytes):
    import Quartz
    from Foundation import NSData

    nsdata = NSData.dataWithBytes_length_(data, len(data))
    src = Quartz.CGImageSourceCreateWithData(nsdata, None)
    if src is None:
        return None
    return Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)


def _vision_recognize(data: bytes, lang: str) -> list[Leitura]:
    import Vision

    cg = _cgimage(data)
    if cg is None:
        return []
    langs = ["pt-BR", "en-US"] if lang in ("por", "pt", "pt-BR") else [lang, "en-US"]
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
    request = Vision.VNRecognizeTextRequest.alloc().init()
    try:
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    except Exception:
        pass
    try:
        request.setRecognitionLanguages_(langs)
        request.setUsesLanguageCorrection_(True)
    except Exception:
        pass

    ok, _err = handler.performRequests_error_([request], None)
    if not ok:
        return []

    leituras: list[Leitura] = []
    for obs in request.results() or []:
        cand = obs.topCandidates_(1)
        if not cand:
            continue
        texto = cand[0].string()
        conf = float(cand[0].confidence())
        bb = obs.boundingBox()  # CGRect normalizado, origem inferior-esquerda
        x, y, w, h = bb.origin.x, bb.origin.y, bb.size.width, bb.size.height
        # converte para origem superior-esquerda (padrão do sistema)
        leituras.append(Leitura(texto=texto, confianca=conf,
                                bbox=[float(x), float(1.0 - y - h), float(w), float(h)]))
    return leituras


# ── Backend 2: PaddleOCR ────────────────────────────────────────────
@lru_cache(maxsize=1)
def _paddle() -> Any | None:
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
        from paddleocr import PaddleOCR
        return PaddleOCR
    except Exception:
        return None


# ── Backend 3: RapidOCR (PP-OCR em ONNX) ────────────────────────────
@lru_cache(maxsize=1)
def _rapid() -> Any | None:
    """PP-OCR — os MESMOS modelos do PaddleOCR — rodando em onnxruntime.

    POR QUE ESTE BACKEND EXISTE

    No Linux desta instalação não havia OCR local nenhum: o Apple Vision é do
    macOS e o PaddleOCR precisa do `paddlepaddle`, que **não publica wheel para
    o Python 3.14** do servidor. Resultado prático: o modo LER caía sempre no
    VLM e ficava refém de crédito na conta — quando o saldo acabou, LER parou.

    O RapidOCR resolve sem trocar de modelo: são os pesos PP-OCR exportados
    para ONNX, executados pelo onnxruntime, que tem wheel para 3.14 e roda bem
    em CPU. Mesma qualidade de reconhecimento do PaddleOCR, sem a dependência
    que não existe para esta versão do Python.
    """
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
        from rapidocr_onnxruntime import RapidOCR
        return RapidOCR
    except Exception:
        return None


class EdgeOCR:
    def __init__(self) -> None:
        self._engine: Any | None = None
        self._rapid_engine: Any | None = None

    def backend(self) -> str | None:
        if _vision() is not None:
            return "apple_vision"
        if _paddle() is not None:
            return "paddleocr"
        if _rapid() is not None:
            return "rapidocr"
        return None

    def available(self) -> bool:
        return self.backend() is not None

    # ── PaddleOCR ───────────────────────────────────────────────
    def _load_paddle(self, lang: str) -> Any:
        PaddleOCR = _paddle()
        if self._engine is None:
            ocr_lang = "latin" if lang in ("por", "pt", "pt-BR") else lang
            self._engine = PaddleOCR(use_angle_cls=True, lang=ocr_lang, show_log=False)
        return self._engine

    def _paddle_recognize(self, image_bytes: bytes, lang: str) -> list[Leitura]:
        from PIL import Image
        import numpy as np

        engine = self._load_paddle(lang)
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        arr = np.asarray(img)
        result = engine.ocr(arr, cls=True)

        leituras: list[Leitura] = []
        for linha in (result[0] if result and result[0] else []):
            box, (texto, conf) = linha[0], linha[1]
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            leituras.append(Leitura(
                texto=texto, confianca=float(conf),
                bbox=[x0 / w, y0 / h, (x1 - x0) / w, (y1 - y0) / h],
            ))
        return leituras

    # ── RapidOCR (PP-OCR em ONNX) ───────────────────────────────
    def _rapid_recognize(self, image_bytes: bytes, lang: str) -> list[Leitura]:
        from PIL import Image
        import numpy as np

        if self._rapid_engine is None:
            # A primeira chamada baixa os modelos (~15 MB) e os guarda em disco;
            # as seguintes só carregam. Instanciar uma vez e reusar mantém a
            # latência do LER na casa dos milissegundos.
            self._rapid_engine = _rapid()()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        resultado, _tempos = self._rapid_engine(np.asarray(img))

        leituras: list[Leitura] = []
        for item in resultado or []:
            box, texto, conf = item[0], item[1], item[2]
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            leituras.append(Leitura(
                texto=texto, confianca=float(conf),
                bbox=[x0 / w, y0 / h, (x1 - x0) / w, (y1 - y0) / h],
            ))
        return leituras

    # ── despacho ────────────────────────────────────────────────
    def recognize(self, image_bytes: bytes, lang: str = "por") -> list[Leitura]:
        backend = self.backend()
        if backend == "apple_vision":
            return _vision_recognize(image_bytes, lang)
        if backend == "paddleocr":
            return self._paddle_recognize(image_bytes, lang)
        if backend == "rapidocr":
            return self._rapid_recognize(image_bytes, lang)
        raise EdgeUnavailableError(
            "OCR edge indisponível (instale pyobjc-framework-Vision no macOS, "
            "paddleocr, ou rapidocr-onnxruntime; ou use o VLM)."
        )


edge_ocr = EdgeOCR()
