## O que muda
<!-- Resumo da mudança e o porquê. Referencie a issue: "Fecha #123". -->

## Tipo
- [ ] Correção de bug
- [ ] Nova funcionalidade
- [ ] Documentação
- [ ] Refatoração / manutenção

## Como testei
<!-- pytest, typecheck, navegador; com/sem caminho edge; com/sem ANTHROPIC_API_KEY. -->

## Capturas
<!-- Se mexeu na interface — só com dados e imagens fictícios (sem rostos, placas ou pessoas reais). -->

## Checklist
- [ ] `pytest -q` passa (e `npm run typecheck`, se mexeu no frontend)
- [ ] Dependências pesadas continuam opcionais (import preguiçoso, degradação graciosa)
- [ ] Nenhuma escrita em PLC/ERP sem confirmação humana
- [ ] Sem segredos, `.env`, bancos, pesos de modelo, URLs RTSP com credenciais ou IPs internos no commit
- [ ] Textos da interface em pt-BR
- [ ] `CHANGELOG.md` atualizado (se visível para o usuário)
