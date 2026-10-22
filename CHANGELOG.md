# Changelog

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não publicado]
### Segurança
- **API fechada por padrão.** Toda rota `/api/*` e todo WebSocket `/ws/*` exigem sessão, por uma dependência global (`app/api/guard.py`). Só ficam públicos o login, a saúde (`/api/health`), o estado de bootstrap e a config pública mínima (`/api/capabilities`). Sem sessão: 401 (WebSocket: close 1008).
- Sessão em cookie `vd_session` HttpOnly + SameSite=Strict (+ Secure em HTTPS), além do `X-Auth-Token`; checagem de `Origin` em escrita e WebSocket autenticados por cookie; validade de 30 dias; limite de tentativas de login por IP.
- Papéis por rota: leitura para todos os logados; escrita (PTZ, gravação, workers…) para operador/admin; WhatsApp, bancos, varredura de rede, cadastro de câmera, configuração e ffmpeg de teste só para admin. A config do WhatsApp nunca devolve o token.
- `/docs`, `/redoc` e `/openapi.json` desligados por padrão (`VISIONDESK_EXPOSE_DOCS=true` para dev).
- Cadastro/revogação de face: operador não altera a face de um admin (fecha tomada de conta pelo login facial).
- Teste de transmissão aérea: comando ffmpeg livre só em desenvolvimento; em produção, só o comando padrão.
- `dev-login` aceito só de loopback, mesmo com `VISIONDESK_DEV_LOGIN` ligado.
### Alterado
- Código do backend sincronizado com a versão em produção (PCP, fases, ordens, árvore de dados, gestão de alterações, leitor multiformato do iaMAC, catálogo de 150 classes-alvo).
### Adicionado
- Publicação do código no GitHub: README, capa, guias de contribuição, licença MIT e página de apresentação (`site/`).
### Alterado
- Exemplos e dados de demonstração sem nomes de clientes reais, IPs da rede local ou credenciais de câmera.
- Cache de modelos do iaMAC passa a ser definido só por `VISIONDESK_MODELS_DIR` (antes havia um caminho local fixo).

## 2026-06-29 — supervisório e VPS
- Supervisório SCADA, design system, leitura de QR pela câmera, página de apresentação e módulo de Cibersegurança.

## 2026-06-27 — VisionDesk v2
- Plataforma de visão industrial edge-first com camada de escala (PostgreSQL/TimescaleDB, MinIO, MQTT, MediaMTX), VPS — Visual Planning System (Tag-ID, Fio Dourado, APS) e módulos de termografia, metrologia, automação industrial e reconhecimento facial.
