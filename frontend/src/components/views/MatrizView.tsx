// Referência: Matriz de Câmeras & Dispositivos (VPS_Matriz_Cameras_Dispositivos.md).
// Onde a câmera entra (origem do dado), tokens, dispositivos, edge, compatibilidade, cenários.

function Card({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section className="bg-panel border border-edge rounded-card p-4">
      <div className="flex items-baseline gap-2 mb-3">
        <h3 className="text-sm font-bold">{title}</h3>
        {sub && <span className="text-[11px] text-muted">{sub}</span>}
      </div>
      {children}
    </section>
  );
}

function Table({ head, rows }: { head: string[]; rows: (string | React.ReactNode)[][] }) {
  return (
    <div className="overflow-x-auto scroll-thin">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="text-left text-muted border-b border-edge">
            {head.map((h, i) => <th key={i} className="py-1.5 pr-3 font-semibold whitespace-nowrap uppercase tracking-wider text-[10px]">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-edge/40 last:border-0">
              {r.map((c, j) => <td key={j} className={"py-1.5 pr-3 align-top " + (j === 0 ? "font-medium text-text" : "text-muted")}>{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const Y = <span className="text-ok font-bold">✅</span>;
const M = <span className="text-warn">⚠️</span>;
const N = <span className="text-nok">❌</span>;

export function MatrizView() {
  return (
    <div className="flex flex-col gap-3 min-h-full">
      <div className="flex items-center gap-3 flex-wrap border-b border-edge pb-2">
        <h2 className="text-base font-bold flex items-center gap-2">📐 Matriz de Câmeras & Dispositivos
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">referência</span>
        </h2>
        <span className="text-xs text-muted">Onde a câmera entra · tokens · dispositivos · baixo custo</span>
      </div>

      <div className="flex-1 scroll-thin space-y-4 pr-1">
        <Card title="A câmera é a origem do dado (P01)" sub="camadas L0–L2">
          <p className="text-xs text-muted mb-3">No VPS a câmera não é acessório de inspeção — toda rastreabilidade nasce de uma câmera ver uma ação. Dois papéis:</p>
          <Table head={["Papel", "O que faz", "Modo"]} rows={[
            ["Gênese", "lê o token que abre/avança a ordem", "LER"],
            ["Observação", "confere a fase (conta, verifica, mede, detecta defeito)", "CONTAR · DESCREVER · ANALISAR"],
          ]} />
          <p className="text-[11px] text-muted mt-2">A mesma câmera, no mesmo ato, identifica a ordem (lê o token) <b>e</b> confere o que acontece.</p>
        </Card>

        <Card title="Tokens — a etiqueta que a câmera lê" sub="portador físico do Tag-ID">
          <Table head={["Token", "Como lê", "Custo", "Melhor para"]} rows={[
            ["QR Code", "decode visual", "baixíssimo", "uso geral, alta densidade"],
            ["DataMatrix", "decode visual", "baixíssimo", "peças pequenas, marcação industrial"],
            ["Código de barras", "decode visual", "baixíssimo", "legado, SKU, embalagem"],
            ["Número impresso (OCR)", "OCR por IA", "zero", "legado sem reetiquetar (nº de OP)"],
            ["Objeto (YOLO)", "detecção por IA", "zero", "item sem etiqueta, por forma"],
            ["RFID / NFC", "leitor RF (não é câmera)", "médio", "sem linha de visada, alto volume"],
          ]} />
          <p className="text-[11px] text-muted mt-2">💡 <b>Token é barato; a inteligência está na câmera + software.</b> Tokens de estação (QR fixo no posto) + token da ordem = carimbo automático "OP entrou nesta ação".</p>
        </Card>

        <Card title="Dispositivos de execução" sub="do mais mobile/barato ao mais robusto">
          <Table head={["Dispositivo", "Mobilidade", "Conexão", "Modos", "Custo", "Melhor uso"]} rows={[
            ["Smartphone", "Alta", "App→RTMP/WS (4G/5G/WiFi)", "LER, CONTAR, DESCREVER", "Baixo", "operador móvel, conferência"],
            ["Tablet", "Média", "App→WiFi", "LER, CONTAR, DESCREVER", "Baixo", "posto semi-fixo, supervisão"],
            ["Osmo Pocket 3/4", "Alta", "UVC (USB) ou RTMP", "todos", "Médio-baixo", "qualidade móvel (gimbal, 1\")"],
            ["Webcam USB (UVC)", "Fixa", "USB→edge/PC", "LER, CONTAR", "Baixíssimo", "posto fixo simples"],
            ["Raspberry Pi + câmera", "Fixa/portátil", "edge próprio→rede", "LER, CONTAR, DESCREVER", "Baixo", "estação fixa barata"],
            ["ESP32-CAM", "Fixa", "WiFi→servidor", "LER (token simples)", "Baixíssimo", "leitor de token por posto"],
            ["Câmera industrial", "Fixa", "GigE/CoaXPress + fieldbus", "todos", "Alto", "linha alta cadência"],
            ["Drone (DJI)", "Aérea", "RTMP via celular", "todos", "Médio-alto", "pátio, estoque externo"],
          ]} />
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card title="Onde processa a inferência (edge)">
            <Table head={["Edge", "Capacidade", "Custo", "Modos"]} rows={[
              ["Próprio smartphone", "leve", "já existe", "LER, CONTAR leve"],
              ["Raspberry Pi 5 (+IA)", "média", "baixo", "LER, CONTAR, DESCREVER"],
              ["Jetson Orin Nano", "boa", "médio", "todos, incl. ANALISAR"],
              ["Jetson Orin", "alta", "médio-alto", "todos, alta cadência"],
              ["PC/servidor com GPU", "alta", "variável", "todos, multi-câmera"],
            ]} />
            <p className="text-[11px] text-muted mt-2">Comece no que já existe (smartphone); suba o edge só onde a fase exigir <b>ANALISAR</b>.</p>
          </Card>

          <Card title="Compatibilidade token × dispositivo">
            <Table head={["Token", "Phone", "Osmo", "Webcam", "RPi", "ESP32", "Indl.", "Drone"]} rows={[
              ["QR Code", Y, Y, Y, Y, Y, Y, Y],
              ["DataMatrix", Y, Y, Y, Y, M, Y, Y],
              ["Cód. barras", Y, Y, Y, Y, M, Y, Y],
              ["OCR (nº)", Y, Y, M, M, N, Y, M],
              ["Objeto (YOLO)", M, Y, M, M, N, Y, Y],
            ]} />
            <p className="text-[11px] text-muted mt-2">{Y} bom · {M} possível c/ limitação · {N} não recomendado</p>
          </Card>
        </div>

        <Card title="Cenários recomendados" sub="mobile + baixo custo">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              ["💸 Ultra baixo custo", "QR/DataMatrix impresso + smartphone do operador + edge no próprio aparelho (4G/WiFi). Modos LER+CONTAR.", "MVP, picking, conferência, tokens de estação"],
              ["🔧 Posto fixo barato", "QR na peça + QR fixo da estação + webcam/ESP32-CAM + Raspberry Pi 5. LER+CONTAR+DESCREVER.", "estações fixas sem câmera industrial"],
              ["🎥 Conferência móvel de qualidade", "Osmo Pocket (UVC local / RTMP móvel) + notebook/Jetson Nano. Todos os modos incl. ANALISAR.", "medições, inspeção, almoxarifado"],
              ["🛸 Área externa / grande porte", "Drone DJI (RTMP via celular). DESCREVER + ANALISAR.", "pátio, estoque externo, ativos"],
            ].map(([t, d, ideal], i) => (
              <div key={i} className="bg-surface border border-edge rounded-card p-3">
                <p className="text-sm font-semibold mb-1">{t}</p>
                <p className="text-[11px] text-muted">{d}</p>
                <p className="text-[10px] text-accent mt-1.5">Ideal: {ideal}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Considerações práticas">
          <Table head={["Tema", "Recomendação"]} rows={[
            ["Iluminação", "fator nº 1 de leitura — garanta luz boa nos postos de token"],
            ["Qualidade do token", "etiqueta limpa, plana, tamanho adequado à distância"],
            ["Confiança", "abaixo do limiar → revisão (não bloqueia); ajustável por fase no template"],
            ["Rede (RTMP)", "privada/VPN; RTMP não é criptografado"],
            ["HTTPS", "obrigatório p/ player web / getUserMedia"],
          ]} />
        </Card>

        <p className="text-[10px] text-muted pb-2">Fonte: VPS_Matriz_Cameras_Dispositivos.md · complementa spec_tecnologia/osmo/Drono e VPS_05/06. As etiquetas QR são geradas no módulo <b>🧵 VPS → 🏷 Etiqueta</b>.</p>
      </div>
    </div>
  );
}
