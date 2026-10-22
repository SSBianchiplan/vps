"""Reconhecimento facial / biometria de operador (edge, LGPD by design).

VisionDesk_Reconhecimento_Facial_Biometria — identificação CONSENTIDA do operador
para login/autoria/acesso, jamais vigilância. Processa no edge e compara por
distância de cosseno a uma GALERIA RESTRITA de operadores autorizados.

Privacidade (pilar): guarda o **template** (vetor), nunca a foto; consentimento
registrado e **revogável**; sempre há fallback não-biométrico (PIN/crachá).

DOIS MOTORES, UMA INTERFACE

  sface  — detecção YuNet + embedding SFace (ONNX via cv2.FaceDetectorYN /
           cv2.FaceRecognizerSF, 128-d). É o motor de produção: mais preciso e
           tolerante a pose/iluminação que o LBP, e o ÚNICO que existe no
           OpenCV 5, que removeu o Haar cascade do núcleo. Foi exatamente isso
           que quebrou o cadastro de face no VPS: cv2 5.0 sem CascadeClassifier
           → AttributeError → 500 na tela de Acesso & Regras.
  lbp    — Haar + descritor LBP (4096-d). Fica como reserva onde o OpenCV é 4.x
           e os modelos ONNX não foram baixados. Zero download.

Templates gravam `algo` e `dim`. Um template LBP não é comparável a um SFace:
o match pula dimensões diferentes e a identificação avisa "recadastre" em vez
de silenciosamente nunca reconhecer ninguém.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ..config import get_settings
from ..db.database import get_connection

# ── motor SFace/YuNet ────────────────────────────────────────────────
_ALGO_SFACE = "sface-yunet-v1"
_DIM_SFACE = 128
# Limiar de cosseno documentado pelo OpenCV para o SFace (mesma pessoa ≥ 0.363).
_THRESH_SFACE = 0.363

# ── motor LBP (reserva) ──────────────────────────────────────────────
_ALGO_LBP = "lbp-edge-v1"
_DIM_LBP = 16 * 256
_THRESH_LBP = 0.62
_FACE = 100

_MIN_FACE = 60            # px mínimos (qualidade)
_MIN_SHARPNESS = 12.0     # variância do Laplaciano (anti-foto borrada / liveness-lite)

_yunet = None
_sface = None
_cascade = None
_engine_cache: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── seleção de motor ─────────────────────────────────────────────────
def _models_dir() -> Path:
    d = getattr(get_settings(), "face_models_dir", None)
    return Path(d) if d else Path("models") / "face"


def _engine() -> str | None:
    """'sface' | 'lbp' | None. Decidido uma vez por processo."""
    global _engine_cache
    if _engine_cache is not None:
        return _engine_cache or None
    try:
        import cv2
    except Exception:  # noqa: BLE001
        _engine_cache = ""
        return None
    md = _models_dir()
    if (hasattr(cv2, "FaceDetectorYN") and hasattr(cv2, "FaceRecognizerSF")
            and (md / "yunet.onnx").exists() and (md / "sface.onnx").exists()):
        _engine_cache = "sface"
    elif hasattr(cv2, "CascadeClassifier"):
        _engine_cache = "lbp"
    else:
        _engine_cache = ""
    return _engine_cache or None


def available() -> bool:
    return _engine() is not None


def engine_info() -> dict[str, Any]:
    e = _engine()
    return {"engine": e, "algo": _algo(), "dim": _dim(), "threshold": _threshold(),
            "models_dir": str(_models_dir())}


def _algo() -> str:
    return _ALGO_SFACE if _engine() == "sface" else _ALGO_LBP


def _dim() -> int:
    return _DIM_SFACE if _engine() == "sface" else _DIM_LBP


def _threshold() -> float:
    return _THRESH_SFACE if _engine() == "sface" else _THRESH_LBP


# ── detectores ───────────────────────────────────────────────────────
def _yunet_det(w: int, h: int):
    global _yunet
    import cv2
    if _yunet is None:
        _yunet = cv2.FaceDetectorYN.create(str(_models_dir() / "yunet.onnx"), "", (w, h), 0.8, 0.3, 50)
    _yunet.setInputSize((w, h))
    return _yunet


def _sface_rec():
    global _sface
    import cv2
    if _sface is None:
        _sface = cv2.FaceRecognizerSF.create(str(_models_dir() / "sface.onnx"), "")
    return _sface


def _haar():
    global _cascade
    import cv2
    if _cascade is None:
        _cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
    return _cascade


def _decode(image_b64: str) -> "np.ndarray | None":
    import base64
    import cv2
    raw = base64.b64decode(image_b64)
    arr = np.frombuffer(raw, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _detect_raw(bgr) -> list[np.ndarray]:
    """Linhas de face no formato do YuNet: [x, y, w, h, 5×(lx, ly), score].

    No motor LBP as linhas são sintetizadas (só bbox), para que o resto do
    módulo trate os dois motores igual.
    """
    import cv2
    H, W = bgr.shape[:2]
    if _engine() == "sface":
        _, faces = _yunet_det(W, H).detect(bgr)
        if faces is None:
            return []
        return [f for f in faces if f[2] >= _MIN_FACE and f[3] >= _MIN_FACE]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    found = _haar().detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(_MIN_FACE, _MIN_FACE))
    return [np.array([x, y, w, h] + [0.0] * 11, dtype=np.float32) for (x, y, w, h) in found]


def detect_faces(bgr) -> list[tuple[int, int, int, int]]:
    """Bboxes (x, y, w, h) das faces — usado também pelo blur LGPD (vps/lgpd.py)."""
    return [(int(f[0]), int(f[1]), int(f[2]), int(f[3])) for f in _detect_raw(bgr)]


# ── descritores ──────────────────────────────────────────────────────
def _lbp_template(gray_face) -> np.ndarray:
    """Descritor LBP por células (espacial) — tolerante a iluminação."""
    import cv2
    g = cv2.resize(gray_face, (_FACE, _FACE))
    g = cv2.equalizeHist(g).astype(np.int16)
    c = g[1:-1, 1:-1]
    codes = np.zeros(c.shape, np.uint8)
    nb = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
    for i, (dy, dx) in enumerate(nb):
        codes |= ((g[1 + dy:g.shape[0] - 1 + dy, 1 + dx:g.shape[1] - 1 + dx] >= c).astype(np.uint8) << i)
    hs, ws = codes.shape[0] // 4, codes.shape[1] // 4
    feats = []
    for by in range(4):
        for bx in range(4):
            cell = codes[by * hs:(by + 1) * hs, bx * ws:(bx + 1) * ws]
            h, _ = np.histogram(cell, bins=256, range=(0, 256))
            feats.append(h)
    v = np.concatenate(feats).astype(np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


def _sface_template(bgr, face_row: np.ndarray) -> np.ndarray:
    rec = _sface_rec()
    aligned = rec.alignCrop(bgr, face_row)
    v = rec.feature(aligned).reshape(-1).astype(np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


def _sharpness(gray_face) -> float:
    import cv2
    return float(cv2.Laplacian(cv2.resize(gray_face, (_FACE, _FACE)), cv2.CV_64F).var())


def _largest(faces: list[np.ndarray]) -> np.ndarray | None:
    return max(faces, key=lambda f: float(f[2] * f[3])) if faces else None


def _embed_b64(image_b64: str) -> dict[str, Any]:
    """Detecta a maior face → (template, qualidade/sharpness, bbox normalizado)."""
    import cv2
    if not available():
        return {"ok": False, "message": "reconhecimento facial indisponível neste host (sem OpenCV ou sem modelos)"}
    bgr = _decode(image_b64)
    if bgr is None:
        return {"ok": False, "message": "imagem inválida"}
    H, W = bgr.shape[:2]
    faces = _detect_raw(bgr)
    f = _largest(faces)
    if f is None:
        return {"ok": False, "message": "nenhuma face detectada"}
    x, y, w, h = (max(0, int(f[0])), max(0, int(f[1])), int(f[2]), int(f[3]))
    crop = bgr[y:y + h, x:x + w]
    if crop.size == 0:
        return {"ok": False, "message": "face fora do quadro"}
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    sharp = _sharpness(gray)
    template = _sface_template(bgr, f) if _engine() == "sface" else _lbp_template(gray)
    return {"ok": True, "template": template, "sharpness": sharp,
            "bbox": [x / W, y / H, w / W, h / H], "live": sharp >= _MIN_SHARPNESS, "faces": len(faces)}


# ── Galeria (operadores autorizados) ─────────────────────────────────
def _row_vec(row: dict[str, Any]) -> np.ndarray:
    return np.asarray(json.loads(row["template_json"]), dtype=np.float32)


def gallery() -> list[dict[str, Any]]:
    rows = get_connection().execute(
        "SELECT operator_id, name, algo, dim, consent_ts, is_current, created_at "
        "FROM vps_face_template WHERE is_current=1 ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        # Template de outro motor não reconhece ninguém — melhor dizer na tela.
        d["compatible"] = d.get("algo") == _algo()
        out.append(d)
    return out


def _current_rows() -> list[dict[str, Any]]:
    return [dict(r) for r in get_connection().execute(
        "SELECT operator_id, name, template_json, algo FROM vps_face_template WHERE is_current=1").fetchall()]


def enroll(operator_id: str, name: str, image_b64: str, consent: bool, consent_ref: str | None = None) -> dict[str, Any]:
    """Cadastra o template de um operador — EXIGE consentimento (LGPD art. 11)."""
    if not consent:
        return {"ok": False, "message": "consentimento obrigatório (biometria é dado sensível)"}
    emb = _embed_b64(image_b64)
    if not emb["ok"]:
        return emb
    if not emb["live"]:
        _event("LIVENESS_FAILED", operator_id, severity="alerta", summary=f"qualidade insuficiente no cadastro de {name}")
        return {"ok": False, "message": "face borrada/baixa qualidade — tente novamente com boa luz e nitidez"}
    get_connection().execute(
        "INSERT INTO vps_face_template(operator_id,name,template_json,algo,dim,consent_ts,consent_ref,is_current,created_at)"
        " VALUES (?,?,?,?,?,?,?,1,?)"
        " ON CONFLICT(operator_id) DO UPDATE SET name=excluded.name, template_json=excluded.template_json,"
        " algo=excluded.algo, dim=excluded.dim, consent_ts=excluded.consent_ts, is_current=1, created_at=excluded.created_at",
        (operator_id, name, json.dumps([round(float(x), 6) for x in emb["template"]]), _algo(), _dim(),
         _now(), consent_ref, _now()))
    _event("BIOMETRIC_ENROLLED", operator_id, summary=f"biometria cadastrada (consentida): {name} · {_algo()}")
    return {"ok": True, "operator_id": operator_id, "name": name, "algo": _algo(), "dim": _dim(),
            "sharpness": round(emb["sharpness"], 1)}


def _best_match(vec: np.ndarray) -> tuple[dict[str, Any] | None, float, int]:
    """(melhor linha, similaridade, nº de templates de outro motor ignorados)."""
    best, best_sim, skipped = None, -1.0, 0
    for r in _current_rows():
        g = _row_vec(r)
        if g.shape != vec.shape:
            skipped += 1
            continue
        sim = float(np.dot(vec, g))  # ambos L2-normalizados → cosseno
        if sim > best_sim:
            best, best_sim = r, sim
    return best, best_sim, skipped


def identify(image_b64: str) -> dict[str, Any]:
    """1:N — descobre o operador na galeria autorizada."""
    emb = _embed_b64(image_b64)
    if not emb["ok"]:
        return emb
    if not emb["live"]:
        _event("LIVENESS_FAILED", None, severity="alerta", summary="tentativa com face de baixa qualidade/spoof")
        return {"ok": True, "live": False, "matched": False, "message": "liveness/qualidade reprovada", "bbox": emb["bbox"]}
    row, sim, skipped = _best_match(emb["template"])
    thr = _threshold()
    matched = bool(row) and sim >= thr
    out = {"ok": True, "live": True, "matched": matched, "score": round(sim, 3),
           "bbox": emb["bbox"], "faces": emb["faces"], "threshold": thr, "algo": _algo()}
    if skipped and not matched:
        out["message"] = (f"{skipped} template(s) cadastrados com outro motor ({'LBP' if _engine() == 'sface' else 'SFace'}) "
                          f"— recadastre a face para reconhecer")
    if matched and row:
        out.update({"operator_id": row["operator_id"], "name": row["name"]})
        _event("OPERATOR_IDENTIFIED", row["operator_id"], summary=f"operador identificado por face: {row['name']} ({sim:.2f})",
               payload={"method": "FACE", "score": round(sim, 3), "algo": _algo()})
    return out


def verify(operator_id: str, image_b64: str) -> dict[str, Any]:
    """1:1 — confirma se é o operador X (login)."""
    emb = _embed_b64(image_b64)
    if not emb["ok"]:
        return emb
    row = get_connection().execute(
        "SELECT operator_id,name,template_json,algo FROM vps_face_template WHERE operator_id=? AND is_current=1",
        (operator_id,)).fetchone()
    if not row:
        return {"ok": False, "message": "operador sem biometria cadastrada"}
    g = _row_vec(dict(row))
    if g.shape != emb["template"].shape:
        return {"ok": False, "message": f"biometria cadastrada com outro motor ({dict(row).get('algo')}) — recadastre a face"}
    sim = float(np.dot(emb["template"], g))
    thr = _threshold()
    ok = emb["live"] and sim >= thr
    _event("ACCESS_GRANTED" if ok else "ACCESS_DENIED", operator_id,
           severity="ok" if ok else "alerta",
           summary=f"login facial {'concedido' if ok else 'negado'}: {dict(row)['name']} ({sim:.2f})",
           payload={"method": "FACE", "score": round(sim, 3), "algo": _algo()})
    return {"ok": True, "verified": ok, "live": emb["live"], "score": round(sim, 3),
            "operator_id": operator_id, "name": dict(row)["name"], "threshold": thr}


def revoke(operator_id: str) -> dict[str, Any]:
    """Revoga o consentimento → apaga o template (direito do titular, LGPD)."""
    cur = get_connection().execute("DELETE FROM vps_face_template WHERE operator_id=?", (operator_id,))
    if cur.rowcount:
        _event("CONSENT_WITHDRAWN", operator_id, severity="alerta", summary=f"consentimento retirado · template apagado: {operator_id}")
    return {"ok": cur.rowcount > 0}


def kpis() -> dict[str, Any]:
    """KPIs CLD_ de autenticação a partir da trilha (eventos de face)."""
    conn = get_connection()

    def n(action: str) -> int:
        try:
            return int(dict(conn.execute(
                "SELECT COUNT(*) AS n FROM audit_event WHERE category='SYSTEM' AND action=?", (action,)).fetchone())["n"])
        except Exception:  # noqa: BLE001
            return 0
    ident, denied, granted = n("OPERATOR_IDENTIFIED") + n("ACCESS_GRANTED"), n("ACCESS_DENIED"), n("ACCESS_GRANTED")
    liveness = n("LIVENESS_FAILED")
    total = ident + denied
    gal = gallery()
    return {
        "enrolled": len(gal),
        "incompatible": sum(1 for g in gal if not g.get("compatible")),
        "CLD_Auth_Success_Rate": round(100 * ident / total, 1) if total else None,
        "CLD_Liveness_Block_Rate": liveness,
        "granted": granted, "denied": denied, "liveness_failed": liveness,
        "threshold": _threshold(), "algo": _algo(), "engine": _engine(), "available": available(),
    }


def _event(action: str, oid: str | None, *, severity: str = "info", summary: str = "", payload: Any = None) -> None:
    try:
        from .. import audit
        audit.record("SYSTEM", action, severity=severity, actor=oid or "face",
                     entity_type="operator", entity_id=oid, summary=summary, payload=payload)
    except Exception:  # noqa: BLE001
        pass
