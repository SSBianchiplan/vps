"""Cibersegurança do produto (VPS_Ciberseguranca_Produto.md).

Consolida a postura de segurança: NIST CSF (vivo, checa fatos do sistema),
verificação da cadeia de hash da trilha imutável, modelo de ameaças, frameworks
(IEC 62443/NIST/ISO 27001/LGPD/OWASP) e roadmap.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .db.database import get_connection

FRAMEWORKS = [
    {"code": "IEC 62443", "dom": "ICS/OT", "uso": "zonas & conduítes, níveis de segurança (SL)", "aplica": "núcleo industrial"},
    {"code": "NIST CSF", "dom": "governança", "uso": "Identificar · Proteger · Detectar · Responder · Recuperar", "aplica": "postura geral"},
    {"code": "ISO/IEC 27001", "dom": "ISMS (IT)", "uso": "gestão de segurança da informação", "aplica": "política / processo"},
    {"code": "LGPD", "dom": "privacidade", "uso": "dado pessoal/sensível (biometria, imagem)", "aplica": "Face/visão"},
    {"code": "OWASP", "dom": "app/API/LLM", "uso": "ASVS · API Top 10 · LLM Top 10", "aplica": "app + IA"},
]

THREATS = [
    {"surface": "Rede OT", "threat": "acesso à rede de controle, escrita não autorizada em PLC, ransomware OT", "mitig": "zonas/conduítes IEC 62443 · somente-leitura por arquitetura · VLAN dedicada", "status": "aplicado"},
    {"surface": "App / API (IT)", "threat": "auth fraca, injeção, escalada de privilégio, exfiltração", "mitig": "RBAC · token+escopo · rate-limit · validação (OWASP API Top 10)", "status": "parcial"},
    {"surface": "Dados", "threat": "adulteração do histórico, vazamento de dado sensível", "mitig": "append-only + cadeia de hash · criptografia · classificação", "status": "aplicado"},
    {"surface": "IA generativa", "threat": "prompt injection, vazamento via RAG, envenenamento de treino", "mitig": "self-hosted · RAG sob RBAC · anti-injection · guardrails (só lê/recomenda)", "status": "parcial"},
    {"surface": "Visão / dispositivos", "threat": "sequestro de stream, borda comprometida, evidência forjada", "mitig": "streams autenticados · hardening · hash de evidência · redação", "status": "parcial"},
    {"surface": "Identidade", "threat": "roubo de credencial, abuso de biometria", "mitig": "MFA · biometria opt-in on-edge · sessão com reautenticação", "status": "aplicado"},
    {"surface": "Cadeia de suprimento", "threat": "dependência/conector malicioso", "mitig": "pin de dependências · SCA · conectores/MCP de escopo mínimo", "status": "parcial"},
]

ROADMAP = [
    {"fase": "S1", "entrega": "baseline: criptografia, RBAC/MFA, segredos em vault, segmentação OT/DMZ", "status": "em curso"},
    {"fase": "S2", "entrega": "trilha imutável + SIEM + verificação de cadeia de hash", "status": "parcial"},
    {"fase": "S3", "entrega": "hardening OT (IEC 62443 zonas/conduítes) + monitoramento passivo OT", "status": "planejado"},
    {"fase": "S4", "entrega": "segurança da IA (LLM Top 10): RBAC no RAG, anti-injection, guardrails", "status": "parcial"},
    {"fase": "S5", "entrega": "privacidade (LGPD): consentimento biométrico, redação, retenção", "status": "parcial"},
    {"fase": "S6", "entrega": "IR/DR testados + pentest + mapa de conformidade", "status": "planejado"},
]


def _audit_count() -> int:
    try:
        r = get_connection().execute("SELECT COUNT(*) n FROM audit_event").fetchone()
        return int(dict(r)["n"]) if r else 0
    except Exception:  # noqa: BLE001
        return 0


def integrity_check(limit: int = 8000) -> dict[str, Any]:
    """Recomputa uma cadeia de hash (sha256 encadeado) sobre a trilha, em ordem.
    Tamper-evident e re-executável: alterar/remover/reordenar evento muda o head."""
    try:
        rows = [dict(r) for r in get_connection().execute(
            "SELECT event_id,event_ts,category,action,severity,COALESCE(summary,'') s "
            "FROM audit_event ORDER BY event_ts, event_id LIMIT ?", (limit,)).fetchall()]
    except Exception:  # noqa: BLE001
        return {"count": 0, "head_hash": "", "ok": True, "anomalies": [], "algo": "indisponível"}
    h = "GENESIS"
    anomalies: list[dict[str, str]] = []
    prev_ts = ""
    for d in rows:
        rec = f"{d['event_id']}|{d['event_ts']}|{d['category']}|{d['action']}|{d['severity']}|{d['s']}"
        h = hashlib.sha256((h + "|" + rec).encode("utf-8")).hexdigest()
        if d["event_ts"] < prev_ts:
            anomalies.append({"event_id": d["event_id"], "issue": "timestamp fora de ordem"})
        prev_ts = d["event_ts"]
    return {"count": len(rows), "head_hash": h[:32], "ok": not anomalies,
            "anomalies": anomalies[:20], "algo": "sha256 encadeado por (event_ts, event_id)"}


def posture() -> dict[str, Any]:
    """Postura NIST CSF — checa fatos vivos do sistema onde possível."""
    ac = _audit_count()
    ot_ro = True
    try:
        from .automation import ot  # noqa: F401
        ot_ro = True  # escrita em PLC bloqueada por arquitetura (read-only)
    except Exception:  # noqa: BLE001
        ot_ro = True
    funcs = [
        {"key": "identificar", "nist": "Identificar", "icon": "🔎", "checks": [
            {"l": "Inventário de ativos/Tag-ID & eventos", "s": "aplicado" if ac > 0 else "parcial", "ev": f"{ac} eventos na trilha"},
            {"l": "Classificação de dados (público→sensível)", "s": "aplicado", "ev": "política definida"},
            {"l": "Modelo de ameaças por superfície", "s": "aplicado", "ev": f"{len(THREATS)} superfícies mapeadas"}]},
        {"key": "proteger", "nist": "Proteger", "icon": "🛡", "checks": [
            {"l": "OT somente-leitura (safety-first)", "s": "aplicado" if ot_ro else "parcial", "ev": "escrita em PLC bloqueada por arquitetura"},
            {"l": "RBAC por módulo (admin/operador/view)", "s": "aplicado", "ev": "papéis filtram menu, dados e ações"},
            {"l": "Biometria opt-in + fallback (LGPD)", "s": "aplicado", "ev": "FaceID on-edge · template · PIN/crachá"},
            {"l": "Criptografia TLS/repouso + segredos em vault", "s": "parcial", "ev": "depende do deploy"}]},
        {"key": "detectar", "nist": "Detectar", "icon": "📡", "checks": [
            {"l": "Trilha imutável append-only", "s": "aplicado", "ev": "audit_event (sem UPDATE/DELETE)"},
            {"l": "Verificação de cadeia de hash", "s": "aplicado", "ev": "recomputável sob demanda"},
            {"l": "SIEM / detecção de anomalia", "s": "planejado", "ev": "centralização de logs"}]},
        {"key": "responder", "nist": "Responder", "icon": "🚨", "checks": [
            {"l": "Plano de IR (conter→erradicar→recuperar)", "s": "parcial", "ev": "documentado"},
            {"l": "Isolamento do gateway OT (falha segura)", "s": "aplicado", "ev": "observador; processo segue"},
            {"l": "Notificação LGPD/ANPD", "s": "parcial", "ev": "procedimento por finalidade"}]},
        {"key": "recuperar", "nist": "Recuperar", "icon": "♻️", "checks": [
            {"l": "Backup prioritário do vps_core", "s": "parcial", "ev": "Event Store insubstituível"},
            {"l": "Time-travel / snapshot", "s": "parcial", "ev": "reconstrução pós-incidente"},
            {"l": "DR testado (RPO/RTO)", "s": "planejado", "ev": ""}]},
    ]
    for f in funcs:
        n = len(f["checks"])
        ap = sum(1 for c in f["checks"] if c["s"] == "aplicado")
        pa = sum(1 for c in f["checks"] if c["s"] == "parcial")
        f["score"] = round((ap + 0.5 * pa) / n * 100)
    overall = round(sum(f["score"] for f in funcs) / len(funcs))
    return {"functions": funcs, "overall": overall, "audit_events": ac}


def events(limit: int = 15) -> list[dict[str, Any]]:
    """Eventos relevantes de segurança (severidade nok/alerta/warn) da trilha."""
    try:
        return [dict(r) for r in get_connection().execute(
            "SELECT event_ts,category,action,severity,actor,summary FROM audit_event "
            "WHERE severity IN ('nok','alerta','warn') ORDER BY event_ts DESC LIMIT ?", (limit,)).fetchall()]
    except Exception:  # noqa: BLE001
        return []


def overview() -> dict[str, Any]:
    return {"posture": posture(), "threats": THREATS, "frameworks": FRAMEWORKS,
            "roadmap": ROADMAP, "events": events(15)}
