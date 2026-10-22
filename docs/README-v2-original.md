> **Nota de publicação (out/2026):** README original do desenvolvimento (VisionDesk v2), mantido como referência técnica.
> As especificações citadas (`spec_visao.md`, `spec_tecnologia.md`, `spec_Drono.md`, `spec_osmo.md` e outras) **não** foram publicadas.
> Portas mudaram desde então: backend em 8200 e frontend em 7777 (veja o README principal).

# VisionDesk

**Sistema de visão computacional configurável** — usa a câmera do MacBook e do
iPhone como sensores e expõe um frontend onde o operador define, em tempo de
execução, qual tarefa a IA executa sobre a imagem:

| Modo | O que faz | Caminho de IA |
|------|-----------|---------------|
| **LER** | Extrai texto/códigos/números (OCR estruturado) | OCR edge (PaddleOCR) → VLM como fallback |
| **CONTAR** | Detecta e conta objetos/pessoas com tracking | YOLO + ByteTrack (edge) → VLM por snapshot |
| **DESCREVER** | Descreve a cena em linguagem natural | VLM (Claude vision) |
| **ANALISAR** | Inspeção de conformidade OK/NOK | VLM estruturado (+ crop de ROI) |

Implementa a baseline `spec_visao.md` (v0.1). Arquitetura agnóstica de domínio,
pensada para contextos industriais (contagem de peças, leitura de OP/etiquetas,
inspeção visual).

> **Princípio de robustez:** o caminho **VLM (Claude) cobre os 4 modos**, então o
> sistema roda de ponta a ponta apenas com a `ANTHROPIC_API_KEY`. O caminho
> **edge** (YOLO/OCR/tracking) é opcional e **degrada graciosamente** — se as
> dependências pesadas não estiverem instaladas, o orquestrador roteia para o
> VLM automaticamente.

---

## Plataforma v2 — visão industrial + escala

Além dos 5 modos, o sistema implementa o catálogo da **`spec_tecnologia.md`** (8 tecnologias de visão industrial) e uma camada de escala:

- **Modelos reais locais (edge, sem token):** YOLO11 (DETECTAR/CONTAR), **CNN** MobileNetV3 + **ViT** B/16 (`/api/classify`), **OCR** Apple Vision, **anomalia não supervisionada** PatchCore-lite via embeddings YOLO (`/api/anomaly`).
- **VLM (Claude):** DESCREVER/ANALISAR + descrição/análise de ciclo. Motor **IA ↔ Local** selecionável por módulo.
- **Sempre-ligado:** workers de câmera contínuos (`/api/workers`) — captura→inferência→persistência 24/7.
- **Gravações por detecção** (pessoa/cachorro etc.) em tabela `fact_recording` + object store.
- **Monitoramento em tempo real:** série de rede/buffer (latência/jitter/throughput) em **TimescaleDB**, gráfico ao vivo.
- **Estúdio com 2 abas:** **Modos** (5, stream contínuo) e **🏭 Tecnologias** (8 modelos rodando na fonte ao vivo, motor IA↔Local). Fonte: dispositivo (MacBook/iPhone/Windows/Android/USB/Outros) ou câmera IP.
- **Módulos de UI:** Indústria (catálogo), Estudo de caso (pipeline na câmera + relatório/diagnóstico), **Bases de Dados** (status de cada armazenamento), Monitoramento (gráfico em tempo real com tendência/média móvel), AGIR (regras no-code + WhatsApp/wa.me). Barra lateral recolhível.
- **Integração industrial (ISA-95):** eventos → **MQTT** (MES/SCADA); **MediaMTX** (WebRTC fan-out); métricas **Prometheus** (`/api/metrics`); auth opcional por API-key.

### Stack de escala (Docker)

```bash
docker compose up -d            # Postgres+TimescaleDB · MinIO · MQTT · MediaMTX
cp .env.docker.example .env     # e mescle no seu .env (DATABASE_URL, S3, MQTT, RESTREAM_BASE)
```

Tudo **degrada graciosamente**: sem `DATABASE_URL` → SQLite; sem S3 → filesystem; sem broker → no-op. Veja o módulo **Bases de Dados** na UI p/ o status de cada armazenamento.

---

## Arquitetura

```
┌──────────────────────── FRONTEND (React + Vite + Tailwind) ────────────────────────┐
│  Configuração (fonte/modo/params/ROI)  ·  Preview + overlay  ·  Stream de resultados │
└──────────────┬─────────────────────────────────────────────────┬───────────────────┘
   getUserMedia │ frames (base64, amostrados)                       │ WebSocket (resultados)
               ▼                                                   ▼
┌──────────────────────────────── BACKEND (FastAPI / Python) ────────────────────────┐
│  Intake de frames  →  Pré-processamento (Pillow)  →  ORQUESTRADOR (roteamento)        │
│                                  ┌───────────────┴───────────────┐                    │
│                          EDGE (YOLO/OCR/ByteTrack)          VLM (Claude vision)        │
│                                  └───────────────┬───────────────┘                    │
│        Pós-processamento (NMS/tracking/regex/validação JSON) → Persistência (SQLite)  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

- **Orquestrador** (`app/orchestrator/router.py`): escolhe edge/vlm/híbrido por
  modo + capacidades disponíveis (Seção 2.1 da spec).
- **Pipelines** (`app/pipelines/`): um por modo, com fallback edge→VLM.
- **VLM** (`app/inference/vlm/claude_client.py`): Claude (`claude-opus-4-8`) com
  **structured outputs** (`output_config.format`) — JSON validado por schema; e
  **adaptive thinking** no modo ANALISAR (julgamento).
- **Edge** (`app/inference/edge/`): YOLO/RT-DETR (Ultralytics) + ByteTrack e OCR,
  com import preguiçoso e degradação graciosa.
- **Dados** (`app/db/`): **star schema** SQLite (DIM_SOURCE/TASK/MODEL +
  FACT_DETECTION/COUNT/OCR) para analytics posterior.

---

## Pré-requisitos

- **macOS (Apple Silicon)** como ambiente primário.
- **Python 3.12** recomendado (3.11–3.14 funcionam para o core; o caminho **edge**
  com `torch/ultralytics` tem melhor suporte de wheels em 3.12).
- **Node 18+**.
- **Chave da API Anthropic** (`ANTHROPIC_API_KEY`) para os modos via VLM.

---

## Setup rápido

### 1) Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # core (roda os 4 modos via VLM)
# (opcional) caminho edge local:
# pip install -r requirements-edge.txt    # YOLO/OCR/tracking (use Python 3.12)

cp ../.env.example ../.env                # e preencha ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

Backend em `http://localhost:8000` (docs em `/docs`, WebSocket em `/ws/stream`).

### 2) Frontend

```bash
cd frontend
npm install
npm run dev                               # http://localhost:5173
```

O Vite faz proxy de `/api` e `/ws` para o backend em dev — nada mais a configurar.
Abra `http://localhost:5173`, conecte a câmera, escolha o modo e clique **Iniciar**.

> **iPhone como câmera:** com o **Continuity Camera** (macOS Ventura+), o iPhone
> aparece como uma câmera comum no seletor — zero código extra.

---

## Uso

1. **Fonte** — conceda permissão e escolha a câmera (MacBook ou iPhone).
2. **Modo** — LER / CONTAR / DESCREVER / ANALISAR.
3. **Parâmetros** — painel dinâmico por modo (regex, classes-alvo, critérios…).
4. **ROI** — desenhe retângulo/linha/zona sobre o vídeo (para foco/contagem/filtro).
5. **Iniciar** (loop contínuo) ou **Snapshot** (uma inferência sob demanda — ideal
   para VLM, economiza custo).
6. **Resultados** — overlay em tempo real + painel + **exportar CSV/JSON**.

### Cadência (Seção 9 da spec)
- CONTAR ~3 fps · LER ~1 fps · DESCREVER/ANALISAR ~1 frame a cada 2,5 s.
- Backpressure: processa o frame mais recente; descarta frames enquanto há um em
  voo (sem acumular backlog).

---

## Teste rápido via REST (sem frontend)

```bash
# imagem -> base64 e inferência DESCREVER
B64=$(base64 -i caminho/para/foto.jpg)
curl -s localhost:8000/api/infer -H 'Content-Type: application/json' -d "{
  \"image_b64\": \"$B64\",
  \"task\": {\"mode\": \"DESCREVER\", \"params\": {\"mode\": \"DESCREVER\", \"foco\": \"a cena\"}}
}" | jq

curl -s localhost:8000/api/capabilities | jq   # mostra edge/vlm disponíveis
```

---

## Câmeras IP na rede (scan + RTSP)

Além da câmera local, o sistema descobre e usa **câmeras IP por Wi-Fi/LAN**:

- **Descoberta** (`GET /api/cameras/scan`): ONVIF WS-Discovery (multicast) + varredura
  das portas comuns (RTSP 554/8554, ONVIF 8000, Dahua 37777, **Xiongmai/ICSee 34567**…)
  no seu `/24` — restrita a sub-redes privadas. Retorna IPs, portas e **URLs RTSP candidatas**.
- **Captura** (`POST /api/cameras/snapshot`): puxa um frame da câmera (RTSP via OpenCV,
  ou HTTP de snapshot via httpx com Digest/Basic) e devolve JPEG base64.

No frontend: fonte **“Câmera IP”** → **🔍 Escanear rede** → escolha uma URL candidata →
informe **usuário/senha** → **Iniciar**. O backend captura os frames e roda a inferência
nos 4 modos, exatamente como na câmera local.

> **RTSP exige OpenCV no backend** (`opencv-python`/`-headless`). Câmeras que expõem um
> endpoint **HTTP de snapshot** funcionam sem OpenCV. Para **ICSee/Xiongmai** (porta 34567),
> o RTSP costuma ser `rtsp://USER:SENHA@IP:554/onvif1` ou
> `rtsp://IP:554/user=admin&password=SENHA&channel=1&stream=0.sdp` (senha definida no app da câmera).

```bash
curl "localhost:8000/api/cameras/scan?timeout=3" | jq          # descobre câmeras
curl -X POST localhost:8000/api/cameras/snapshot -H 'Content-Type: application/json' \
  -d '{"url":"rtsp://192.168.1.64:554/onvif1","username":"admin","password":"..."}' | jq .media_type
```

## Modelo de dados (star schema)

`DIM_SOURCE`, `DIM_TASK`, `DIM_MODEL` (dimensões de configuração) e
`FACT_DETECTION` (grão = 1 inferência), `FACT_COUNT` (janela de contagem),
`FACT_OCR` (campo reconhecido). Veja `backend/app/db/schema.sql`. Migração para
PostgreSQL é direta (trocar a camada `db/database.py`).

---

## Segurança e privacidade (Seção 10)

- **Processamento local prioritário**: só sobe ao VLM o que for necessário.
- **Frames não são persistidos por padrão** — só metadados/resultados. Ative com
  `VISIONDESK_PERSIST_FRAMES=true` (opt-in) se autorizado.
- Chave de API **apenas no backend** (variável de ambiente), nunca no frontend.
- Permissão de câmera explícita; avalie LGPD antes de persistir imagens com pessoas.

---

## Testes

```bash
cd backend && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q          # 23 testes: roteamento, schemas, pipelines (VLM mockado), contagem
```

---

## Roadmap (mapeado à spec)

| Fase | Estado neste repositório |
|------|--------------------------|
| 0 — Fundação (captura dual-source + WS) | ✅ |
| 1 — DESCREVER (MVP IA) | ✅ |
| 2 — LER (OCR + ROI + regex) | ✅ (VLM completo; OCR edge opcional) |
| 3 — CONTAR (YOLO + tracking + linha/zona) | ✅ código (requer `requirements-edge.txt`); fallback VLM ✅ |
| 4 — ANALISAR (OK/NOK + crop híbrido) | ✅ |
| 5 — Industrialização (WebRTC, Postgres/TimescaleDB, MinIO, MQTT, métricas) | ✅ stack docker + adapters (degradação graciosa) |
| 6 — Catálogo industrial: CNN/ViT/Anomalia/Edge/Sintéticos + workers contínuos | ✅ modelos reais locais + `/api/classify` `/api/anomaly` `/api/workers` |

---

## Estrutura

```
backend/app/
  config.py · main.py · logging_conf.py
  schemas/      enums, tasks, results, messages (contratos)
  db/           schema.sql, database, repository (star schema)
  preprocessing/ image_ops (resize/crop/realce)
  inference/
    vlm/        claude_client, prompts (structured outputs)
    edge/       detector (YOLO), ocr (Paddle) — degradação graciosa
  tracking/     line_counter (cruzamento de linha / zona)
  orchestrator/ router (roteamento edge/vlm/híbrido)
  pipelines/    read / count / describe / analyze
  api/          REST (tasks/sources/export/infer/health) + ws (WebSocket)
frontend/src/
  components/   ConfigPanel, PreviewPanel, CanvasOverlay, ResultsPanel, params/*
  hooks/        useCamera   ·   api/ ws, client   ·   store/ useStore (zustand)
```

---

*GPlanSiS — baseline v0.1.*
