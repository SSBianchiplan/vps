# Política de segurança

## Versões suportadas
| Versão | Suporte |
|---|---|
| `main` (VisionDesk v2 / VPS 0.1) | ✅ |
| anteriores | ❌ |

## Como relatar uma vulnerabilidade
**Não abra issue pública.** Envie um e-mail para **contato@gplansis.com** com o assunto `[SEGURANÇA] GPlanSiS|VisionDesk VPS`, contendo:
- descrição do problema e impacto;
- passos para reproduzir (ou prova de conceito);
- versão, navegador e ambiente usados.

Confirmamos o recebimento assim que possível, mantemos você informado sobre a correção e damos crédito na publicação, se desejar.

## Escopo
Autenticação (PIN, crachá, FaceID), RBAC do VPS, guarda por API key, WebSocket de frames, descoberta e credenciais de câmeras, integração OT (deve permanecer somente leitura), trilha de auditoria encadeada, biometria e tratamento de imagens (LGPD).

## Avisos para quem implanta
- O papel padrão de desenvolvimento é `Admin` (`VISIONDESK_VPS_DEFAULT_ROLE`): troque antes de expor o sistema e defina `VISIONDESK_API_KEY`.
- `ops/mosquitto.conf` (broker anônimo) e `ops/mediamtx.yml` (API aberta) são só para desenvolvimento.
- Senhas do `docker-compose.yml` são de desenvolvimento — use segredos próprios em produção.

Testes devem ser feitos numa instância local — **não** teste contra vps.gplansis.com nem contra câmeras ou redes de terceiros.
