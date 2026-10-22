"""Aplicação FastAPI do VisionDesk: REST + WebSocket."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
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
    asyncio.create_task(asyncio.to_thread(_warmup_edge))
    yield
    from .workers import manager
    await manager.stop_all()
    close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VisionDesk",
        description="Sistema de visão computacional configurável (LER/CONTAR/DESCREVER/ANALISAR).",
        version="0.1.0",
        lifespan=lifespan,
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
    app.include_router(routes_security.router, prefix="/api")
    app.include_router(ws.router)
    app.include_router(ws_devices.router)
    app.include_router(ws_vps.router)

    @app.get("/")
    def root() -> dict:
        return {
            "service": "VisionDesk",
            "version": "0.1.0",
            "docs": "/docs",
            "ws": "/ws/stream",
        }

    return app


app = create_app()
