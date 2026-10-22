"""Reconhecimento facial / biometria de operador (edge, LGPD by design).

VisionDesk_Reconhecimento_Facial_Biometria — identificação CONSENTIDA do operador
para login/autoria/acesso, jamais vigilância. Processa no edge (cv2 Haar p/
detecção + descritor LBP p/ template) e compara por distância de cosseno a uma
GALERIA RESTRITA de operadores autorizados.

Privacidade (pilar): guarda o **template** (vetor), nunca a foto; consentimento
registrado e **revogável**; sempre há fallback não-biométrico (PIN/crachá).

Nota de engenharia: o descritor LBP roda 100% local e sem download de modelo.
Em produção, trocar por ArcFace/SFace (ONNX via cv2.FaceRecognizerSF) — a
interface (enroll/identify/verify) permanece a mesma.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import numpy as np

from ..db.database import get_connection

_ALGO = "lbp-edge-v1"
_DIM = 16 * 256  # 4×4 células × 256 bins
_FACE = 100      # face normalizada (px)
_MATCH_THRESHOLD = 0.62   # cosseno mínimo p/ match (calibrável)
_MIN_FACE = 60            # px mínimos (qualidade)
_MIN_SHARPNESS = 12.0     # variância do Laplaciano (anti-foto borrada / liveness-lite)

_cascade = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def available() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _detector():
    global _cascade
    if _cascade is None:
        import cv2
        _cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
    return _cascade


def _decode(image_b64: str) -> "np.ndarray | None":
    import base64
    import cv2
    raw = base64.b64decode(image_b64)
    arr = np.frombuffer(raw, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def detect_faces(bgr) -> list[tuple[int, int, int, int]]:
    import cv2
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = _detector().detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(_MIN_FACE, _MIN_FACE))
    return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]


def _lbp_template(gray_face) -> np.ndarray:
    """Descritor LBP por células (espacial) — tolerante a iluminação."""
    import cv2
    g = cv2.resize(gray_face, (_FACE, _FACE))
    g = cv2.equalizeHist(g).astype(np.int16)
    # LBP 8-vizinhos (vetorizado)
    c = g[1:-1, 1:-1]
    codes = np.zeros(c.shape, np.uint8)
    nb = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
    for i, (dy, dx) in enumerate(nb):
        codes |= ((g[1 + dy:g.shape[0] - 1 + dy, 1 + dx:g.shape[1] - 1 + dx] >= c).astype(np.uint8) << i)
    # histograma por 4×4 células
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


def _sharpness(gray_face) -> float:
    import cv2
    return float(cv2.Laplacian(cv2.resize(gray_face, (_FACE, _FACE)), cv2.CV_64F).var())


def _largest(faces: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int] | None:
    return max(faces, key=lambda f: f[2] * f[3]) if faces else None


def _embed_b64(image_b64: str) -> dict[str, Any]:
    """Detecta a maior face → (template, qualidade/sharpness, bbox normalizado)."""
    import cv2
    bgr = _decode(image_b64)
    if bgr is None:
        return {"ok": False, "message": "imagem inválida"}
    H, W = bgr.shape[:2]
    faces = detect_faces(bgr)
    f = _largest(faces)
    if not f:
        return {"ok": False, "message": "nenhuma face detectada"}
    x, y, w, h = f
    gray = cv2.cvtColor(bgr[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
    sharp = _sharpness(gray)
    return {"ok": True, "template": _lbp_template(gray), "sharpness": sharp,
            "bbox": [x / W, y / H, w / W, h / H], "live": sharp >= _MIN_SHARPNESS, "faces": len(faces)}


# ── Galeria (operadores autorizados) ─────────────────────────────────
def _row_vec(row: dict[str, Any]) -> np.ndarray:
    return np.asarray(json.loads(row["template_json"]), dtype=np.float32)


def gallery() -> list[dict[str, Any]]:
    rows = get_connection().execute(
        "SELECT operator_id, name, algo, dim, consent_ts, is_current, created_at "
        "FROM vps_face_template WHERE is_current=1 ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def _current_rows() -> list[dict[str, Any]]:
    return [dict(r) for r in get_connection().execute(
        "SELECT operator_id, name, template_json FROM vps_face_template WHERE is_current=1").fetchall()]


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
        (operator_id, name, json.dumps([round(float(x), 6) for x in emb["template"]]), _ALGO, _DIM,
         _now(), consent_ref, _now()))
    _event("BIOMETRIC_ENROLLED", operator_id, summary=f"biometria cadastrada (consentida): {name}")
    return {"ok": True, "operator_id": operator_id, "name": name, "algo": _ALGO, "dim": _DIM, "sharpness": round(emb["sharpness"], 1)}


def _best_match(vec: np.ndarray) -> tuple[dict[str, Any] | None, float]:
    best, best_sim = None, -1.0
    for r in _current_rows():
        g = _row_vec(r)
        if g.shape != vec.shape:
            continue
        sim = float(np.dot(vec, g))  # ambos L2-normalizados → cosseno
        if sim > best_sim:
            best, best_sim = r, sim
    return best, best_sim


def identify(image_b64: str) -> dict[str, Any]:
    """1:N — descobre o operador na galeria autorizada."""
    emb = _embed_b64(image_b64)
    if not emb["ok"]:
        return emb
    if not emb["live"]:
        _event("LIVENESS_FAILED", None, severity="alerta", summary="tentativa com face de baixa qualidade/spoof")
        return {"ok": True, "live": False, "matched": False, "message": "liveness/qualidade reprovada", "bbox": emb["bbox"]}
    row, sim = _best_match(emb["template"])
    matched = bool(row) and sim >= _MATCH_THRESHOLD
    out = {"ok": True, "live": True, "matched": matched, "score": round(sim, 3),
           "bbox": emb["bbox"], "faces": emb["faces"], "threshold": _MATCH_THRESHOLD}
    if matched and row:
        out.update({"operator_id": row["operator_id"], "name": row["name"]})
        _event("OPERATOR_IDENTIFIED", row["operator_id"], summary=f"operador identificado por face: {row['name']} ({sim:.2f})",
               payload={"method": "FACE", "score": round(sim, 3)})
    return out


def verify(operator_id: str, image_b64: str) -> dict[str, Any]:
    """1:1 — confirma se é o operador X (login)."""
    emb = _embed_b64(image_b64)
    if not emb["ok"]:
        return emb
    row = get_connection().execute(
        "SELECT operator_id,name,template_json FROM vps_face_template WHERE operator_id=? AND is_current=1",
        (operator_id,)).fetchone()
    if not row:
        return {"ok": False, "message": "operador sem biometria cadastrada"}
    sim = float(np.dot(emb["template"], _row_vec(dict(row))))
    ok = emb["live"] and sim >= _MATCH_THRESHOLD
    _event("ACCESS_GRANTED" if ok else "ACCESS_DENIED", operator_id,
           severity="ok" if ok else "alerta",
           summary=f"login facial {'concedido' if ok else 'negado'}: {dict(row)['name']} ({sim:.2f})",
           payload={"method": "FACE", "score": round(sim, 3)})
    return {"ok": True, "verified": ok, "live": emb["live"], "score": round(sim, 3),
            "operator_id": operator_id, "name": dict(row)["name"], "threshold": _MATCH_THRESHOLD}


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
    return {
        "enrolled": len(gallery()),
        "CLD_Auth_Success_Rate": round(100 * ident / total, 1) if total else None,
        "CLD_Liveness_Block_Rate": liveness,
        "granted": granted, "denied": denied, "liveness_failed": liveness,
        "threshold": _MATCH_THRESHOLD, "algo": _ALGO,
    }


def _event(action: str, operator_id: str | None, *, severity: str = "info",
           summary: str = "", payload: Any = None) -> None:
    """Evento de biometria na trilha — score/método, NUNCA a imagem facial."""
    try:
        from .. import audit
        audit.record("SYSTEM", action, severity=severity, actor=operator_id or "face",
                     entity_type="operator", entity_id=operator_id, summary=summary, payload=payload)
    except Exception:  # noqa: BLE001
        pass
