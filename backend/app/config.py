"""Configuração central do VisionDesk (via variáveis de ambiente / .env)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações carregadas de variáveis de ambiente com prefixo VISIONDESK_.

    A chave da Anthropic usa o nome padrão do SDK (ANTHROPIC_API_KEY, sem prefixo)
    para que o cliente Anthropic a resolva automaticamente.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_prefix="VISIONDESK_",
        extra="ignore",
        case_sensitive=False,
    )

    # ── VLM (Claude) ────────────────────────────────────────────
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    claude_model: str = "claude-opus-4-8"
    vlm_max_tokens: int = 4096

    # ── Persistência ────────────────────────────────────────────
    db_path: str = "./data/visiondesk.db"
    persist_frames: bool = False
    frames_dir: str = "./data/frames"

    # ── Servidor ────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8200   # evita conflito com o ProjectAnalyzer (:8000)
    # CSV de origens (string para evitar o parsing JSON de campos complexos do
    # pydantic-settings ao vir do .env). Use cors_origins_list para a lista.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:7777,http://127.0.0.1:7777"

    # ── Edge (opcional) ─────────────────────────────────────────
    # YOLO26 e a familia mais nova (NMS-free, mais rapida em CPU que a YOLO11).
    # A variante -objv1 e treinada no Objects365: 365 classes em vez das 80 do
    # COCO, pelo mesmo custo (250 ms vs 217 ms em 1 vCPU, medido). E o que faz o
    # catalogo de 150 classes-alvo (target_classes.py) ser real e nao promessa.
    # 78 das 80 classes COCO existem com o mesmo nome — regras salvas seguem
    # valendo. O "s" e o maior porte dentro dos ~200 ms/frame que a spec cobra.
    # Nome sem caminho = o Ultralytics baixa sozinho no primeiro uso.
    yolo_weights: str = "yolo26s-objv1-150.pt"
    yolo_conf: float = 0.35
    edge_device: str = "mps"  # mps | cpu | cuda

    # ── Escala / integração (todos opcionais — degradam p/ no-op) ──
    api_key: str | None = None              # se setado, exige X-API-Key em /api/* (#8)
    # Atalho "Entrar como DEV Admin" (POST /api/auth/dev-login). Ligado por
    # padrão para o desenvolvimento local; DESLIGUE em qualquer deploy exposto
    # à internet (VISIONDESK_DEV_LOGIN=false) — ele dá sessão de admin sem PIN.
    dev_login: bool = True
    # Documentação interativa (/docs, /redoc, /openapi.json). Desligada por
    # padrão: em produção ela entregava o mapa das 228 rotas a qualquer um.
    # Para desenvolvimento local: VISIONDESK_EXPOSE_DOCS=true.
    expose_docs: bool = False
    # Sessão: validade do token em horas (0 = sem expiração) e flag Secure do
    # cookie (vazio = automático: Secure quando o pedido chega por HTTPS).
    session_ttl_hours: float = 720.0
    cookie_secure: bool | None = None
    database_url: str | None = None         # postgres://… (#2) — vazio = SQLite local
    s3_endpoint: str | None = None          # MinIO/S3 p/ frames/gravações (#2)
    s3_bucket: str = "visiondesk"
    mqtt_url: str | None = None             # ex.: mqtt://broker:1883 (#7)
    mqtt_topic: str = "visiondesk/events"
    opcua_url: str | None = None            # ex.: opc.tcp://host:4840 (#7)
    restream_base: str | None = None        # base do media server (MediaMTX/go2rtc) p/ WebRTC (#3)
    # ── Visão Aérea (drone via RTMP→MediaMTX→player) — spec_Drono.md ──
    restream_api_base: str | None = None     # API MediaMTX p/ status (default :9997)
    aerial_path: str = "drone_neo2"          # path/stream-key publicado pelo DJI Fly
    aerial_osmo_path: str = "osmo_pocket"    # path do DJI Osmo Pocket (spec_osmo.md)
    aerial_rtmp_host: str | None = None       # host p/ o DRONE (quem empurra é o celular c/ Tailscale)
    aerial_osmo_rtmp_host: str | None = None  # host p/ o OSMO (quem empurra é a CÂMERA, na WiFi local → IP da LAN)
    # ── VPS (Visual Planning System) — ponte Visão→Fio Dourado ──
    vps_auto_capture: bool = True             # LER vira gênese; CONTAR/ANALISAR viram verificação
    vps_segment: str = "PANEL"                # segmento default p/ Tag-IDs gerados da visão
    vps_pending_cost_per_hour: float = 50.0   # custo/hora de pendência aberta (CLD_Cost_of_Pendencies)
    vps_currency: str = "R$"
    vps_lgpd_blur: bool = False               # LGPD: borra rostos nos frames salvos (§15)
    vps_retention_days: int = 90              # LGPD: retenção de imagens/gravações (dias)
    vps_default_role: str = "Admin"     # RBAC: papel default (dev aberto); UI envia X-VPS-Role

    # ── Reconhecimento facial (edge) ────────────────────────────
    # Pasta com yunet.onnx + sface.onnx (OpenCV Zoo). Com eles o motor e o SFace
    # (128-d); sem eles cai no Haar+LBP — que NAO existe no OpenCV 5, e foi por
    # isso que o cadastro de face quebrou no VPS. Relativo ao cwd do servico.
    face_models_dir: str = "models/face"

    # ── iaMAC (RAG extrativo) ───────────────────────────────────
    # Diretórios EXTRA de conhecimento, CSV. O corpus base são os .md na raiz
    # do repositório — que num deploy só-código (app/) simplesmente não existem,
    # e o RAG sobe com 1 chunk (só o snapshot ao vivo) sem dizer que está vazio.
    # Aqui entram as specs copiadas para o servidor e o módulo GPlanSIS·HSkills
    # (skills e agentes), lidos recursivamente.
    iamac_corpus_dirs: str | None = None
    # Biblioteca GERENCIAVEL do iaMAC: a pasta onde a interface faz upload/remocao
    # de documentos (PDF, Word, Excel, PowerPoint, HTML, texto). Default: ao lado
    # do banco. Lida pelo mesmo leitor multiformato dos diretorios acima.
    iamac_library_dir: str | None = None

    @property
    def aerial_whep_base(self) -> str:
        return (self.restream_base or "http://localhost:8889").rstrip("/")

    @property
    def aerial_api_base(self) -> str:
        return (self.restream_api_base or "http://localhost:9997").rstrip("/")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def vlm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    def db_file(self) -> Path:
        p = Path(self.db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def frames_path(self) -> Path:
        p = Path(self.frames_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
