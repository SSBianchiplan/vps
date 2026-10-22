import { useState } from "react";
import { useStore } from "../../store/useStore";
import type { View } from "../../store/useStore";
import { PLAYBOOK, type TechPlay } from "../../lib/playbook";

function Phase({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-accent mb-0.5">{title}</div>
      <ul className="text-xs text-muted space-y-0.5 list-disc pl-4">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </div>
  );
}

function PlaybookItem({ t }: { t: TechPlay }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-edge rounded-card overflow-hidden">
      <button className="vd-keep w-full flex items-center gap-2 px-3 py-2 bg-edge/50 hover:bg-edge text-left" onClick={() => setOpen((v) => !v)}>
        <span className="text-xs font-mono text-accent">{t.num}</span>
        <span className="text-sm font-semibold flex-1">{t.nome}</span>
        <span className="text-muted">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="p-3 space-y-3">
          <div className="grid sm:grid-cols-2 gap-3">
            <Phase title="1 · Requisitos" items={t.requisitos} />
            <Phase title="2 · Desenvolvimento" items={t.desenvolvimento} />
            <Phase title="3 · Validação" items={t.validacao} />
            <Phase title="4 · Testes" items={t.testes} />
            <Phase title="5 · Implementação" items={t.implementacao} />
            <div className="space-y-2">
              <Phase title="🔧 Equip. necessário" items={t.equipNecessario} />
              <Phase title="⭐ Equip. recomendado" items={t.equipRecomendado} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function H({ children }: { children: React.ReactNode }) {
  return <h3 className="text-sm font-bold text-text mt-1 mb-1.5 flex items-center gap-2">{children}</h3>;
}
function P({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={"text-sm text-muted leading-relaxed " + (className ?? "")}>{children}</p>;
}
function Card({ id, icon, title, children, go }: {
  id?: string; icon: string; title: string; children: React.ReactNode; go?: View;
}) {
  const setView = useStore((s) => s.setView);
  return (
    <section id={id} className="vd-surface border border-edge rounded-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl">{icon}</span>
        <h2 className="font-bold text-base">{title}</h2>
        {go && (
          <button className="vd-keep ml-auto text-xs text-accent hover:underline" onClick={() => setView(go)}>
            abrir →
          </button>
        )}
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}
function Step({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <div className="flex gap-2 text-sm">
      <span className="shrink-0 w-5 h-5 rounded-full bg-accent text-onaccent text-[11px] flex items-center justify-center font-bold">{n}</span>
      <span className="text-text">{children}</span>
    </div>
  );
}

export function ManualView() {
  return (
    <div className="h-full overflow-y-auto scroll-thin pr-1">
      <div className="max-w-3xl mx-auto space-y-4 pb-8">
        <div>
          <h1 className="text-2xl font-bold">Manual do VisionDesk + VPS</h1>
          <P>
            Sistema de visão computacional configurável: usa câmeras (do dispositivo ou IP/Wi-Fi)
            como sensores e executa tarefas de IA sobre a imagem — ler, contar, detectar, descrever,
            analisar — e <b>age</b> (notifica/integra) sobre os resultados.
          </P>
          <P className="mt-1">
            Sobre essa base roda o <b className="text-text">VPS — Visual Planning System</b>: a câmera vê uma ação,
            lê um <b>Tag-ID</b> e abre o <b>Fio Dourado</b> (linhagem rastreável ponta a ponta). Projeto rege →
            card planeja → liberação vira execução (gênese) → a visão realimenta o plano. Tudo é
            <b> dado vinculado a dado</b>, governado, reconciliável e auditável.
          </P>
        </div>

        <Card icon="🚀" title="Começo rápido">
          <Step n={1}>Em <b>Câmeras</b>, clique <b>Escanear rede</b> para achar câmeras IP, ou use a câmera do dispositivo no <b>Estúdio</b>.</Step>
          <Step n={2}>No <b>Painel</b> você vê todas as câmeras ao vivo (grade 1/4/9). Clique numa para abrir o detalhe (ao vivo, PTZ, gravações, eventos).</Step>
          <Step n={3}>No <b>Estúdio</b>, escolha a fonte + o <b>modo</b> (Ler/Contar/Detectar/Descrever/Analisar), ajuste parâmetros e clique <b>▶ Iniciar</b>.</Step>
          <Step n={4}>Em <b>Ações</b>, configure o <b>WhatsApp</b> e crie regras para ser notificado de detecções/inspeções.</Step>
          <div className="border-t border-edge/50 my-1" />
          <Step n={5}><b>VPS — fluxo do chão:</b> em <b>Planejamento</b> crie um projeto → adicione cards → <b>Agendar</b> → <b>Baseline</b> → <b>▶ Liberar</b> (vira Tag-ID/OP).</Step>
          <Step n={6}>Em <b>Operadores → Estação</b>: identifique-se e <b>📷 Aponte/Escaneie</b> o QR da etiqueta → escolha a <b>ação</b> → registra no Fio. Acompanhe tudo no cockpit <b>VPS</b> (board, timeline, KPIs) e o plano×real no <b>APS</b>.</Step>
        </Card>

        <Card icon="🧭" title="Menu — módulos (agrupado)">
          <P className="text-[11px]">Menu lateral em <b>7 blocos</b>: Home + 6 grupos recolhíveis (abre tudo recolhido; clique no título para expandir). Visibilidade por <b>papel (RBAC)</b>: Viewer só lê Home/VPS/Eventos/Modais/Downloads/Manual.</P>
          <ul className="text-sm text-muted space-y-1.5 mt-1">
            <li><b className="text-text">🏠 Home</b> — visão geral, KPIs do dia, câmeras ao vivo.</li>
            <li><b className="text-text">👁 Operações</b> — <b>Monitoramento</b> (sinal IoT, board ao vivo, latência/jitter/throughput) · <b>Câmeras</b> (dispositivos & estações) · <b>Drone</b> (RTMP) · <b>Vídeos</b> (Osmo/evidências).</li>
            <li><b className="text-text">🧠 IA</b> — <b>Análise CV</b> (Estúdio: LER/CONTAR/DETECTAR/DESCREVER/ANALISAR) · <b>Modelos</b> (8 tecnologias industriais) · <b>Casos de Uso</b> · <b>Ações</b> (AGIR/automação).</li>
            <li><b className="text-text">📈 Analytics</b> — <b>VPS Visual Planning System</b> (cockpit/Fio Dourado) · <b>Eventos</b> (event store) · <b>Modais &amp; Vínculos</b> (dado vinculado a dado) · <b>Downloads</b>.</li>
            <li><b className="text-text">📅 Planejamento</b> — <b>Visual Planning</b> (projetos &amp; cards) · <b>APS</b> (sequenciamento por capacidade finita).</li>
            <li><b className="text-text">🏭 Ativos</b> — <b>Operadores</b> (gente/papéis/skills + Estação/scanner) · <b>Câmeras &amp; Tokens</b> (matriz de dispositivos) · <b>Bases</b> (schemas/dados/snapshot).</li>
            <li><b className="text-text">⚙ Administração</b> — <b>Testes</b> (E2E/demo) · <b>Manual</b> (este guia). <b className="text-text">⚙ Aparência</b> no rodapé.</li>
            <li className="text-[11px]">Dica: recolha a barra no botão <b className="text-text">‹/›</b> (vira ícones com tooltip). Auto-recolhe em telas &lt; 820px. Layout responsivo, página rola sem fim.</li>
          </ul>
        </Card>

        <Card icon="🎛" title="Modos de análise (Estúdio)" go="estudio">
          <div className="space-y-2 text-sm">
            <div><H>🔤 LER</H><P>OCR estruturado: extrai texto/números/códigos. Use ROI para focar (ex.: etiqueta), regex para validar e “campos lógicos” (ex.: n_op) para nomear o que foi lido.</P></div>
            <div><H>🔢 CONTAR</H><P>Conta objetos/pessoas com rastreamento (YOLO+ByteTrack). Desenhe uma <b>linha</b> (cruzamentos) ou <b>zona</b> (dentro da área). Edge local; cai para VLM por snapshot se necessário.</P></div>
            <div><H>🎯 DETECTAR <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/15 text-accent">YOLO</span></H><P>Detecção de objetos com caixas + classe + confiança (Ultralytics/YOLO). Sem contagem/tracking — ideal para vigilância. Marque <b>🔔 Notificar</b> para enviar WhatsApp ao detectar classes-alvo (ex.: <i>person</i>).</P></div>
            <div><H>📝 DESCREVER</H><P>Descrição da cena em linguagem natural (Claude). Use o campo de instrução para guiar o foco.</P></div>
            <div><H>✅ ANALISAR</H><P>Inspeção OK/NOK por critérios/rubrica (VLM com raciocínio). Veredito auditável; combine com AGIR para agir no NOK.</P></div>
            <div><H>🏭 Aba Tecnologias</H><P>Laboratório das 8 tecnologias industriais rodando <b>na fonte ao vivo</b> (one-shot): CNN/ViT (classificação), YOLO/Edge (detecção), Anomalia (treina a cena normal → score), VLM (descrição de ciclo), Sintéticos/Imageamento (variações/modalidades). Motor <b>IA ↔ Local</b> por tecnologia.</P></div>
          </div>
        </Card>

        <Card icon="📷" title="Câmeras IP" go="cameras">
          <Step n={1}><b>Escanear rede</b> (ONVIF + portas RTSP) ou cadastrar manual (IP, porta 554, caminho /onvif1, usuário, senha).</Step>
          <Step n={2}>A câmera aparece ao vivo via <b>stream MJPEG</b> de baixa latência. Clique para o <b>detalhe</b>: snapshot, PTZ (câmeras móveis), abas Ao vivo/Gravações/Eventos.</Step>
          <P>Dica: câmeras Wi-Fi noturnas (HEVC/IR) podem ter FPS baixo — habilite o <b>substream</b> H264 no app da câmera ou use rede cabeada para vídeo mais fluido.</P>
        </Card>

        <Card icon="⚡" title="AGIR + Notificações (WhatsApp)" go="acoes">
          <P>AGIR fecha o ciclo <b>visão → decisão → ação</b> sem código.</P>
          <H>Ativar WhatsApp (Meta Cloud API)</H>
          <Step n={1}>Em <a className="text-accent underline" href="https://developers.facebook.com/docs/whatsapp/cloud-api/get-started" target="_blank" rel="noreferrer">developers.facebook.com</a> crie um App (tipo <b>Business</b>) e adicione o produto <b>WhatsApp</b>. Anote o <b>Access Token</b> (temporário 24h ou um System User permanente) e o <b>Phone Number ID</b> do número de teste.</Step>
          <Step n={2}>Ainda no painel da Meta, adicione e <b>verifique</b> os números <b>destinatários</b> de teste (formato E.164: 55DDDNÚMERO).</Step>
          <Step n={3}>Em <b>Ações → Notificações (WhatsApp)</b>: cole Token, Phone Number ID e destinatários. No campo <b>Template</b> use <code>hello_world</code> / <code>en_US</code> e clique <b>Testar</b> (deve chegar a mensagem).</Step>
          <Step n={4}>Para alertas com texto próprio, crie um <b>template aprovado</b> na Meta (corpo com variável, ex.: “Alerta VisionDesk: {"{{1}}"}”), informe o nome/idioma aqui e marque <b>“template tem variável”</b>.</Step>
          <P className="text-[11px]">
            ⚠ Regra da Meta: mensagem <b>iniciada pela empresa</b> (como nossas notificações) só é entregue
            via <b>template aprovado</b>. Texto livre só chega dentro da <b>janela de 24h</b> após o usuário responder.
          </P>
          <H>Regras AGIR</H>
          <Step n={1}><b>SE</b> um campo do resultado bate a condição (ex.: <code>veredito == NOK</code>, <code>contagens.person &gt; 0</code>) <b>ENTÃO</b> dispare ações.</Step>
          <Step n={2}>Ações: <b>whatsapp</b>, webhook, Slack, alerta visual, copiar, log CSV — auditadas (com retry).</Step>
          <P>Atalho: no modo <b>DETECTAR</b>, marque <b>🔔 Notificar</b> para WhatsApp automático ao detectar (cooldown 60s/classe; throttle global 8s anti-flood).</P>
        </Card>

        <Card icon="🏭" title="Indústria — modelos de visão (spec_tecnologia)" go="industria">
          <P>Catálogo prescritivo para incorporar visão a um sistema industrial (Industry 4.0 / ISA-95). Uma aba por tecnologia, com quando usar/não usar, requisitos, I/O, latência, integração e KPI.</P>
          <ul className="text-sm text-muted space-y-1 list-disc pl-5">
            <li><b className="text-text">CNN (3.1)</b> defeito superficial · <b className="text-text">YOLO (3.2)</b> detectar/contar/montagem · <b className="text-text">ViT (3.3)</b> contexto global.</li>
            <li><b className="text-text">Anomalia (3.4)</b> defeito raro/inédito · <b className="text-text">VLM (3.5)</b> análise de ciclo/segurança.</li>
            <li>Transversais: <b className="text-text">Edge AI (3.6)</b> deploy · <b className="text-text">Sintéticos (3.7)</b> treino · <b className="text-text">Imageamento (3.8)</b> captura (térmica/raio-X/3D).</li>
          </ul>
          <P className="text-[11px]">Cada aba mostra o status no VisionDesk: ✅ implementado (YOLO, VLM, Edge), ◐ parcial (CNN, imageamento IR), ○ roadmap.</P>
        </Card>

        <Card icon="🧪" title="Estudo de caso — aplicado às câmeras" go="estudocaso">
          <P>Roda o pipeline industrial <b>CAPTURE → PREPROCESS → INFER → DECIDE → ACT</b> numa câmera real: snapshot → YOLO no edge → regra (classe-alvo presente → FAIL/alarme) → ação (WhatsApp/gravação/MES).</P>
          <Step n={1}>Escolha uma câmera salva e clique <b>▶ Rodar inspeção</b>.</Step>
          <Step n={2}>Veja KPIs (latência de inferência, Result PASS/FAIL), o evento <code>GLX_FACT_VISION_EVENT</code> preenchido e o mapeamento ISA-95 do piloto.</Step>
        </Card>

        {/* ───────────────── VPS — Visual Planning System ───────────────── */}
        <div className="pt-2">
          <div className="flex items-center gap-2">
            <span className="h-px flex-1 bg-edge" />
            <span className="text-[11px] uppercase tracking-[0.18em] text-accent font-bold">VPS · Visual Planning System</span>
            <span className="h-px flex-1 bg-edge" />
          </div>
        </div>

        <Card icon="🧵" title="VPS — conceito & Fio Dourado" go="vps">
          <P>O VPS transforma cada ação do chão em <b>dado rastreável</b>. A câmera (ou o operador) lê um <b>Tag-ID</b> e abre/avança um <b>Fio Dourado</b>: a linhagem completa de uma entidade, do nascimento à entrega.</P>
          <H>🏷 Tag-ID (a chave de tudo)</H>
          <P>Formato <code>VPS:segmento:entidade:chave_natural:instância</code> — ex.: <code>VPS:MANUF:OP:OP-2026-014:1</code>. Entidades: <b>SO</b> (pedido), <b>OP</b> (ordem), <b>PROJ</b> (projeto), <b>ITEM</b>, <b>OCC</b> (ocorrência). É o que vai impresso no QR da etiqueta.</P>
          <H>🔁 Máquina de estados (template por segmento)</H>
          <P>Cada entidade segue um <b>template</b> de fases em ordem (ex. <i>SO_OTC</i>: SO_CREATED→…→DELIVERED; <i>PROJ</i>: ENGINEERING→PRODUCTION→QC→…; <i>FOOD</i>/<i>PHARMA</i>: INTAKE→PROCESSING→PACKAGING→QC). O Kanban do cockpit mostra as colunas <b>nessa ordem de processo</b>.</P>
          <H>⚙ Como funciona por dentro</H>
          <ul className="text-sm text-muted space-y-1 list-disc pl-5">
            <li><b className="text-text">Event sourcing</b>: tudo é evento append-only (imutável). O board/KPIs são <b>projeções</b> (CQRS) reconstruídas dos eventos.</li>
            <li><b className="text-text">Gênese</b>: liberar um card no Planejamento (ou ler o QR pela 1ª vez) emite <code>OP_OPENED</code> e cria a Tag — nasce o Fio.</li>
            <li><b className="text-text">Linhagem</b>: PROJ→OP→fases ficam ligados num grafo; abra a <b>timeline</b> de qualquer Tag para ver o fio inteiro.</li>
            <li><b className="text-text">Ponte de visão</b>: toda inferência da câmera (modo LER) que casa um Tag-ID vira evento VPS automaticamente, carimbando o operador da estação.</li>
          </ul>
          <P className="text-[11px]">Demo: no cockpit use <b>Semear demo</b> (ou Bases → importar Teste Sistema) para popular OPs, linhagem e reconciliação.</P>
        </Card>

        <Card icon="🗂" title="Planejamento (Visual Planning) — como operar" go="planejamento">
          <P>O <b>projeto rege</b> a execução: planeje em cards, agende, congele uma baseline e libere para o chão. A partir da liberação, a realidade (visão/scanner) é comparada ao plano.</P>
          <Step n={1}><b>Criar projeto</b> → emite a Tag <code>PROJ</code> e o evento <code>PROJECT_CREATED</code>.</Step>
          <Step n={2}>Monte a <b>WBS</b> e adicione <b>cards</b> (esforço, recurso, datas) e <b>dependências</b> (FS/SS/FF/SF + lag).</Step>
          <Step n={3}><b>Agendar</b> → roda <b>CPM</b> (ES/EF/LS/LF/folga, caminho crítico) + capacidade finita → grava o cenário do projeto.</Step>
          <Step n={4}><b>Baseline</b> → congela o plano (snapshot) para medir aderência depois.</Step>
          <Step n={5}><b>▶ Liberar card</b> → <b>gênese</b>: cria a Tag <code>OP</code> filha do PROJ, liga a linhagem e joga a OP no cockpit/estação.</Step>
          <P>Acompanhe <b>% concluído</b> (vem das fases observadas), <b>SPI</b> e <b>plano × real</b> direto no card.</P>
        </Card>

        <Card icon="📅" title="APS — sequenciamento (capacidade finita)" go="aps">
          <P>O APS responde <i>“dá pra entregar e quando?”</i> respeitando recursos, skills e calendário. Gantt plano×real, gargalos e simulação.</P>
          <ul className="text-sm text-muted space-y-1 list-disc pl-5">
            <li><b className="text-text">Sequenciamento</b>: lanes por recurso/skill, prioridade e <b>capacidade finita</b> (makespan, changeover).</li>
            <li><b className="text-text">Utilização & gargalo</b>: carga por recurso, identifica o limitante.</li>
            <li><b className="text-text">What-if</b>: compara cenários (adicionar turno, mudar prioridade) antes de publicar.</li>
            <li><b className="text-text">CTP/ATP</b>: data prometível p/ um novo pedido dada a carga atual.</li>
            <li><b className="text-text">Expedite / Replano</b>: prioriza uma OP urgente ou re-otimiza após desvio.</li>
            <li><b className="text-text">Publicar</b> → emite <code>SCHEDULE_PUBLISHED</code> no Fio (o plano vira oficial).</li>
          </ul>
        </Card>

        <Card icon="👷" title="Operadores & Estação (scanner QR) — como operar" go="operadores">
          <P>Cadastro de gente (papéis, skills) com histórico <b>SCD2</b> e a <b>Estação</b> onde o chão registra produção lendo o QR da etiqueta.</P>
          <H>Operar a Estação</H>
          <Step n={1}><b>Identifique-se</b> (operador) — toda leitura fica carimbada com quem fez.</Step>
          <Step n={2}>Escolha a <b>fonte</b>: câmera local, <b>mobile</b> (Android/iOS), <b>IP</b>, <b>Osmo</b> ou <b>drone</b>. Se o navegador pedir, clique <b>Permitir câmera</b> (precisa HTTPS/contexto seguro).</Step>
          <Step n={3}><b>📷 Apontar / Escanear</b> (modo LER) lê o Tag-ID do QR → abre um <b>card com a OP</b> e as <b>ações válidas</b> daquela fase.</Step>
          <Step n={4}><b>Escolha a ação</b> (avançar fase, concluir operação, ou <b>abrir ocorrência</b>) → confirma → grava o evento no Fio.</Step>
          <P className="text-[11px]">Erros de câmera tratados: bloqueada (NotAllowed) → botão Permitir; sem câmera (NotFound); em uso (NotReadable). O scanner usa o detector de QR nativo.</P>
        </Card>

        <Card icon="🏷" title="Gerador de Etiquetas (QR)">
          <P>Gera etiquetas <b>imprimíveis</b> com o Tag-ID em <b>QR</b> (segno) + texto OCR-friendly. É o que a Estação lê. Imprima e cole na peça/ordem/pallet — o QR carrega o Fio Dourado.</P>
          <P className="text-[11px]">A mesma etiqueta serve para humano (lê o número) e máquina (lê o QR). Vincula direto à entidade no cockpit.</P>
        </Card>

        <Card icon="📋" title="Modais & Vínculos (dado vinculado a dado)" go="modais">
          <P>Hub de navegação do grafo: a partir de qualquer objeto, abra modais com suas origens e relações — <b>MD</b> (mestre), <b>TAG</b>, <b>LIN</b> (linhagem), <b>EVT</b> (eventos), <b>PROJ</b>, <b>VIS</b> (visão), <b>TPL</b> (template), <b>REC</b> (reconciliação), <b>CALC</b> (KPIs), <b>IN</b> (entradas). Tudo é clicável e rastreável.</P>
        </Card>

        <Card icon="📐" title="Câmeras & Tokens (Matriz CV)" go="matriz">
          <P>Matriz de <b>dispositivos × tokens</b>: relaciona cada câmera/estação ao que ela pode ler e a que segmento/linha serve. É a referência de cobertura de visão do chão.</P>
        </Card>

        <Card icon="🗄" title="Bases & Teste Sistema (PostgreSQL)" go="bases">
          <P>Status de cada base e o projeto de referência <b>teste_sistema</b> (Postgres): <b>8 schemas</b> — event store append-only (com trigger de imutabilidade + partições), mestre SCD2, projetos, APS, reconciliação, gold/BI e staging.</P>
          <Step n={1}>Veja os schemas e relacionamentos no módulo <b>Bases</b>.</Step>
          <Step n={2}><b>Importar Teste Sistema</b> → traz as <b>10 OPs</b> (Fio completo + linhagem + recon + APS) do Postgres para o app, e os dados aparecem no cockpit VPS.</Step>
          <P className="text-[11px]">Runtime do app é SQLite; o Postgres é o alvo de migração/escala. Seed: <code>scripts/seed_teste_sistema.py</code> (~447 linhas).</P>
        </Card>

        <Card icon="🧪" title="Teste ponta a ponta (E2E)" go="e2e">
          <P>Roda o fluxo real <b>em tela, passo a passo</b>: cria projeto → libera OP (gênese) → leitura de visão avança fases → reconcilia com ERP → calcula KPIs. Serve de demo viva e de verificação de que todos os vínculos estão de pé.</P>
        </Card>

        <Card icon="📊" title="Métricas (KPIs CLD_)">
          <P>O cockpit calcula KPIs <code>CLD_*</code> a partir dos eventos (gold/BI usa <code>GLX_*</code>). Principais:</P>
          <ul className="text-sm text-muted space-y-1 list-disc pl-5">
            <li><b className="text-text">Fluxo</b>: <code>CLD_Active_Threads</code> / <code>CLD_Completed_Threads</code> (Fios em curso/fechados), <code>CLD_Thread_LeadTime_h</code> (lead time), <code>CLD_Operations</code>, <code>CLD_Events_Total</code>.</li>
            <li><b className="text-text">Pontualidade</b>: <code>CLD_OTIF</code>, <code>CLD_Cards_OnTime</code>/<code>Done</code>/<code>Total</code>, <code>CLD_Project_Pct_Complete</code>, <code>CLD_Project_SPI</code>.</li>
            <li><b className="text-text">Plano × real</b>: <code>CLD_Baseline_Adherence</code>, <code>CLD_Schedule_Adherence(_APS)</code>, <code>CLD_Schedule_Variance_min</code>, <code>CLD_Makespan_h</code>, <code>CLD_Replan_Suggested</code>.</li>
            <li><b className="text-text">Capacidade</b>: <code>CLD_Capacity_Utilization</code>, <code>CLD_Resources</code>, <code>CLD_Changeover_Time_min</code>.</li>
            <li><b className="text-text">Qualidade/Pendência</b>: <code>CLD_Occurrence_Open</code>, <code>CLD_Pending_Open</code>, <code>CLD_Breached_Ops</code>, <code>CLD_Cost_of_Pendencies</code>.</li>
            <li><b className="text-text">Visão & recon</b>: <code>CLD_Vision_Coverage</code>, <code>CLD_Inference_Latency_ms</code>, <code>CLD_Reconciliation_Rate</code>.</li>
          </ul>
        </Card>

        <Card icon="🔒" title="Lógica & governança">
          <ul className="text-sm text-muted space-y-1 list-disc pl-5">
            <li><b className="text-text">Imutabilidade</b>: event store append-only; correções são novos eventos (nunca update/delete). Auditoria total.</li>
            <li><b className="text-text">RBAC</b>: papel define o que cada um vê/faz (Admin/Supervisor/Operador/Viewer). Troque o papel e o menu/ações se ajustam.</li>
            <li><b className="text-text">LGPD</b>: rostos podem ser borrados (blur por detecção facial) antes de persistir/exibir evidência.</li>
            <li><b className="text-text">Reconciliação</b>: cruza o que a visão registrou com o documento do ERP/MES; <code>CLD_Reconciliation_Rate</code> mede o casamento, divergências viram ocorrência.</li>
            <li><b className="text-text">Baseline</b>: snapshot do plano para medir desvio sem perder o histórico.</li>
          </ul>
        </Card>

        <Card icon="🧠" title="Como aplicar cada tecnologia — passo a passo" go="industria">
          <P>
            Para cada tecnologia do catálogo (spec_tecnologia), o ciclo de engenharia: <b className="text-text">Requisitos →
            Desenvolvimento → Validação → Testes → Implementação</b>, com os <b className="text-text">equipamentos</b> necessários e recomendados.
            Abra cada uma:
          </P>
          <div className="space-y-2">
            {PLAYBOOK.map((t) => <PlaybookItem key={t.id} t={t} />)}
          </div>
          <P className="text-[11px]">
            Regra de ouro: defina <b>iluminação + câmera + tempo de ciclo</b> ANTES do modelo (§4.3). A decisão binária
            vai ao PLC por fieldbus determinístico; o payload rico (imagem/máscara/score) vai ao MES por TCP/IP.
          </P>
        </Card>

        <Card icon="📈" title="Plano comercial & estratégia de vendas">
          <P>Go-to-market do VisionDesk como <b className="text-text">produto + serviço</b> (visão industrial configurável, edge-first, sem vendor lock-in de nuvem).</P>

          <H>🎯 Posicionamento & ICP</H>
          <ul className="text-sm text-muted space-y-1 list-disc pl-5">
            <li><b className="text-text">ICP:</b> manufatura discreta e processo (auto-peças, alimentos/bebidas, eletrônica, madeireira/florestal, logística) com linhas onde a inspeção manual limita OEE.</li>
            <li><b className="text-text">Dor:</b> defeito que escapa, retrabalho, parada não planejada, rastreabilidade fraca, custo de superqualidade (false-reject).</li>
            <li><b className="text-text">Proposta de valor:</b> reduzir não-qualidade e elevar OEE reaproveitando câmeras existentes; do PoC ao chão de fábrica sem reprojeto.</li>
            <li><b className="text-text">Diferencial:</b> 8 tecnologias num só produto, edge sem token, integra PLC/MES/SCADA (ISA-95), dado vira BI.</li>
          </ul>

          <H>🪜 Funil & motanha de adoção (land & expand)</H>
          <div className="space-y-1.5">
            <Step n={1}><b>Diagnóstico gratuito</b> (1 visita): mapeia defeito-alvo, iluminação, tempo de ciclo, câmeras instaladas. Entrega: relatório de viabilidade + ROI estimado.</Step>
            <Step n={2}><b>PoC pago</b> (2–4 sem): 1 estação, anomalia não-supervisionada (cold-start) + YOLO. KPI de aceite: detection rate / false-reject. Usa o <b>Estudo de caso</b> do sistema como demo.</Step>
            <Step n={3}><b>Piloto de linha</b> (1–3 meses): integração PLC/MES, rastreabilidade (GLX_FACT_VISION_EVENT), dashboards de OEE/retrabalho.</Step>
            <Step n={4}><b>Rollout</b> (expand): replicar por estações/linhas/plantas; contrato recorrente.</Step>
          </div>

          <H>💵 Modelo de receita</H>
          <ul className="text-sm text-muted space-y-1 list-disc pl-5">
            <li><b className="text-text">Setup/Implantação</b> (one-time): engenharia de visão, iluminação, integração, treino de modelo.</li>
            <li><b className="text-text">Licença/Assinatura</b> por estação/câmera (SaaS edge): software, atualizações de modelo (OTA), suporte.</li>
            <li><b className="text-text">Hardware</b> (revenda/BOM): edge (Jetson/Hailo), câmeras, iluminação — margem + integração.</li>
            <li><b className="text-text">Serviços recorrentes:</b> retraining, novos defeitos, SLA, consultoria de processo (VLM/insights).</li>
            <li><b className="text-text">Upsell:</b> imageamento avançado (térmica/raio-X/3D), módulos novos, dashboards executivos.</li>
          </ul>

          <H>📣 Canais & prova</H>
          <ul className="text-sm text-muted space-y-1 list-disc pl-5">
            <li>Venda consultiva direta (eng. de aplicação) + parcerias com integradores de automação e fornecedores de câmera/iluminação.</li>
            <li>Prova: demo ao vivo (Estudo de caso), case com KPI (% defeito, OEE, retrabalho), calculadora de ROI (custo de não-qualidade evitado).</li>
            <li>Conteúdo técnico (este catálogo/manual) como geração de demanda no ecossistema Industry 4.0.</li>
          </ul>

          <H>📊 KPIs comerciais & metas</H>
          <ul className="text-sm text-muted space-y-1 list-disc pl-5">
            <li>Taxa de conversão diagnóstico→PoC→piloto→rollout; ticket médio; receita recorrente (MRR/ARR); CAC/LTV.</li>
            <li>Tempo até valor (PoC ≤ 4 sem); NRR via expand; nº de estações ativas (CLD_Model_Coverage).</li>
          </ul>
          <P className="text-[11px]">Âncora de ROI: pilotos do setor reportam ~3% de yield e ~10% menos retrabalho — use o custo de não-qualidade evitado como justificativa de CapEx faseado.</P>
        </Card>

        <Card icon="🛠" title="Boas práticas & limites">
          <ul className="text-sm text-muted space-y-1 list-disc pl-5">
            <li>Modos via VLM (Descrever/Analisar e fallbacks) exigem a chave da API configurada no backend.</li>
            <li>Detectar/Contar por edge exigem YOLO (Ultralytics) instalado; sem ele, há fallback por VLM (snapshot).</li>
            <li>Senhas de câmera e token do WhatsApp ficam só no backend (arquivos gitignored) — nunca no navegador.</li>
            <li>Personalize tudo em <b>⚙ Aparência</b> (tema, cor, densidade, gráficos) — aplica a todo o sistema.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
