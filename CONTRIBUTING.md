# Como contribuir com o GPlanSiS|VisionDesk VPS

Obrigado pelo interesse! Este guia explica como propor mudanças de forma que a revisão seja rápida.

## Antes de começar
- Leia o [código de conduta](CODE_OF_CONDUCT.md).
- Para mudanças maiores que uma correção pontual, **abra uma issue primeiro** (modelos "Ideia" ou "Bug") e combine a abordagem.
- Falhas de segurança **não** vão em issue pública: siga a [política de segurança](SECURITY.md).

## Ambiente de desenvolvimento
```bash
cp .env.example .env          # ANTHROPIC_API_KEY é opcional
make backend                  # FastAPI em http://localhost:8200 (docs em /docs)
make frontend                 # Vite em http://localhost:7777
make test                     # pytest do backend
```
O caminho edge (YOLO/OCR/tracking) é opcional: `make install-edge` (use Python 3.12).

## Organização do código
- `backend/app/orchestrator/` e `pipelines/` — roteamento edge/VLM e um pipeline por modo.
- `backend/app/inference/` — clientes do Claude (VLM) e modelos locais (edge), sempre com import preguiçoso e degradação graciosa.
- `backend/app/vps/` — Tag-ID, Fio Dourado, APS, planejamento, reconciliação, RBAC e LGPD.
- `backend/app/api/` — rotas REST e WebSocket.
- `frontend/src/components/views/` — um componente por módulo do menu.

## Regras do projeto
- **Interface em português do Brasil**, textos curtos e diretos.
- **A IA propõe, o humano confirma**: nenhuma ação automática escreve no processo (PLC, ERP) sem confirmação; integração OT é somente leitura.
- **Degradação graciosa**: dependência pesada (OpenCV, Ultralytics, torch, MLX) nunca pode quebrar o import do backend.
- **Privacidade**: não persistir frames por padrão; biometria só com consentimento; nada de rosto, placa ou pessoa real em testes, issues ou capturas.
- Nunca inclua `.env`, bancos (`data/`), pesos de modelos, certificados, **URLs RTSP com usuário/senha** ou IPs da sua rede em commits.
- Python: siga o estilo do arquivo (tipagem, funções curtas); rode `pytest -q` antes de enviar. Frontend: `npm run typecheck`.

## Pull requests
1. Faça um fork e crie uma branch a partir de `main` (`feat/…`, `fix/…`, `docs/…`).
2. Commits pequenos, com mensagem no imperativo explicando o porquê.
3. Preencha o modelo do PR: o que mudou, como testou (com e sem edge/VLM), capturas se mexer na interface.
4. Atualize o `CHANGELOG.md` quando a mudança for visível para quem usa.

## Dúvidas
Abra uma issue com o modelo "Pergunta" ou escreva para contato@gplansis.com.
