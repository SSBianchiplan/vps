"""Aplicação FastAPI do VisionDesk: REST + WebSocket."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db.database import close_db, init_db
from .logging_conf import configure_logging, get_logger
from .api import (
    routes_actions,
    routes_aerial,
    routes_auth,
    routes_automation,
    routes_anomaly,
    routes_cameras,
    routes_changes,
    routes_classify,
    routes_config,
    routes_databases,
    routes_events,
    routes_export,
    routes_face,
    routes_health,
    routes_iamac,
    routes_infer,
    routes_metro,
    routes_metrics,
    routes_monitor,
    routes_notify,
    routes_recordings,
    routes_security,
    routes_sources,
    routes_tasks,
    routes_thermo,
    routes_vps,
    routes_workers,
    ws,
    ws_devices,
    ws_vps,
)

configure_logging()
log = get_logger("visiondesk")


def _warmup_edge() -> None:
    """Aquece os motores edge (1ª inferência é lenta: carrega modelos do SO).
    Roda em thread no startup para que a 1ª requisição do usuário seja rápida."""
    import io

    from PIL import Image

    from .inference.edge.ocr import edge_ocr

    try:
        if edge_ocr.available():
            buf = io.BytesIO()
            Image.new("RGB", (48, 24), "white").save(buf, "JPEG")
            edge_ocr.recognize(buf.getvalue(), "por")
            log.info("OCR edge aquecido (backend=%s)", edge_ocr.backend())
    except Exception:  # noqa: BLE001
        log.exception("falha no warmup do OCR edge (não fatal)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    settings = get_settings()
    init_db()
    log.info("VisionDesk iniciado | modelo VLM=%s | VLM=%s", settings.claude_model, settings.vlm_enabled)
    if not settings.vlm_enabled:
        log.warning("ANTHROPIC_API_KEY ausente — modos via VLM ficarão indisponíveis.")
    # Câmeras desligadas (raiz) não devem streamar nem após restart.
    try:
        from .discovery import saved, stream
        stream.sync_blocked([c["ip"] for c in saved.list_public() if not c.get("enabled", True)])
    except Exception:  # noqa: BLE001
        log.exception("falha ao sincronizar câmeras desligadas (não fatal)")
    # Todo usuário do sistema é também operador do chão de fábrica (uma pessoa,
    # um cadastro). Idempotente: só escreve quem ainda não tem espelho.
    try:
        from .auth import auth as _auth
        _auth.sync_operators()
    except Exception:  # noqa: BLE001
        log.exception("sync usuários→operadores falhou (não fatal)")
    asyncio.create_task(asyncio.to_thread(_warmup_edge))
    yield
    from .workers import manager
    await manager.stop_all()
    close_db()


def create_app() -> FastAPI:
    import asyncio
    from .api import guard
    settings = get_settings()
    docs = settings.expose_docs
    app = FastAPI(
        title="VisionDesk",
        description="Sistema de visão computacional configurável (LER/CONTAR/DESCREVER/ANALISAR).",
        version="0.1.0",
        lifespan=lifespan,
        # Auditoria out/2026 (C3): /docs, /redoc e /openapi.json só com
        # VISIONDESK_EXPOSE_DOCS=true (desenvolvimento). Em produção, 404.
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
        # Portão GLOBAL: toda rota /api/* e /ws/* exige sessão, salvo a lista
        # PUBLIC de guard.py (login, health, config pública mínima).
        dependencies=[Depends(guard.require_session)],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth opcional (#8): se VISIONDESK_API_KEY setado, exige X-API-Key em /api/*
    # (exceto health/metrics). Default: sem auth (dev).
    if settings.api_key:
        from fastapi import Request
        from fastapi.responses import JSONResponse

        _OPEN = ("/api/health", "/api/metrics")

        @app.middleware("http")
        async def _api_key_guard(request: Request, call_next):
            path = request.url.path
            if path.startswith("/api/") and not path.startswith(_OPEN):
                if request.headers.get("x-api-key") != settings.api_key:
                    return JSONResponse({"detail": {"code": "unauthorized", "message": "X-API-Key inválida"}}, status_code=401)
            return await call_next(request)

    # Gestão de alterações: publica quem está agindo para os triggers do banco.
    # Fica ANTES dos routers para valer em toda mutação, inclusive as que não
    # passam pela trilha da aplicação.
    @app.middleware("http")
    async def _publica_ator(request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                from .auth import auth as _auth
                from .db.database import set_actor
                s = await asyncio.to_thread(_auth.session, request.headers.get("x-auth-token"))
                # set_actor só grava no ContextVar; quem aplica no Postgres é
                # get_connection(), já na thread e na conexão que vai escrever.
                set_actor((s or {}).get("operator_id"), request.url.path)
            except Exception:  # noqa: BLE001
                pass
        return await call_next(request)

    # Cookie de sessão → X-Auth-Token. Adicionado por ÚLTIMO para ser o
    # middleware mais externo: tudo abaixo (inclusive _publica_ator) já vê o
    # cabeçalho.
    app.add_middleware(guard.SessionCookieBridge)

    # REST sob /api; WebSocket na raiz (/ws/stream).
    app.include_router(routes_health.router, prefix="/api")
    app.include_router(routes_tasks.router, prefix="/api")
    app.include_router(routes_sources.router, prefix="/api")
    app.include_router(routes_export.router, prefix="/api")
    app.include_router(routes_infer.router, prefix="/api")
    app.include_router(routes_cameras.router, prefix="/api")
    app.include_router(routes_aerial.router, prefix="/api")
    app.include_router(routes_events.router, prefix="/api")
    app.include_router(routes_monitor.router, prefix="/api")
    app.include_router(routes_actions.router, prefix="/api")
    app.include_router(routes_notify.router, prefix="/api")
    app.include_router(routes_recordings.router, prefix="/api")
    app.include_router(routes_anomaly.router, prefix="/api")
    app.include_router(routes_classify.router, prefix="/api")
    app.include_router(routes_databases.router, prefix="/api")
    app.include_router(routes_workers.router, prefix="/api")
    app.include_router(routes_metrics.router, prefix="/api")
    app.include_router(routes_vps.router, prefix="/api")
    app.include_router(routes_face.router, prefix="/api")
    app.include_router(routes_thermo.router, prefix="/api")
    app.include_router(routes_metro.router, prefix="/api")
    app.include_router(routes_iamac.router, prefix="/api")
    app.include_router(routes_auth.router, prefix="/api")
    app.include_router(routes_automation.router, prefix="/api")
    app.include_router(routes_config.router, prefix="/api")
    app.include_router(routes_changes.router, prefix="/api")
    app.include_router(routes_security.router, prefix="/api")
    app.include_router(ws.router)
    app.include_router(ws_devices.router)
    app.include_router(ws_vps.router)

    @app.get("/")
    def root() -> dict:
        return {
            "service": "VisionDesk",
            "version": "0.1.0",
            "docs": "/docs" if docs else None,
            "ws": "/ws/stream",
        }

    return app


app = create_app()
