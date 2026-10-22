import { StreamPanel } from "../StreamPanel";

export function AerialView() {
  return (
    <StreamPanel
      path="drone_neo2"
      icon="🛸"
      title="Visão Aérea"
      subtitle="DJI Neo 2 · RTMP → MediaMTX → WebRTC"
      offlineHint="drone offline — inicie o RTMP no DJI Fly (ver instruções →)"
      testLabel="Testar sem drone"
      opTitle="Operação (DJI Fly)"
      rtmpLabel="RTMP (cole no DJI Fly)"
      latencyText="latência ~3–6 s (piso do DJI Fly)"
      steps={<>
        <li>Celular no <b>WiFi do drone</b> + <b>dado 4G/5G ativo</b>.</li>
        <li>DJI Fly → Transmission → <b>RTMP</b>.</li>
        <li>Endereço RTMP abaixo; <b>1080p / 4–5 Mbps</b> → Start (máx. qualidade do Neo 2). Se travar no upload, baixe p/ 720p/2 Mbps.</li>
        <li>Badge fica <b className="text-nok">● AO VIVO</b> → o player conecta sozinho.</li>
      </>}
      extras={
        <details className="text-xs">
          <summary className="cursor-pointer text-muted hover:text-text select-none">🔒 VPN Tailscale (acesso pelo 4G) — passo a passo</summary>
          <ol className="list-decimal pl-4 mt-2 space-y-1 text-text">
            <li>Instale o <b>Tailscale</b> no <b>Mac</b> (servidor) e no <b>celular</b> (App Store/Play).</li>
            <li>Login com a <b>mesma conta</b> nos dois → entram no mesmo “tailnet”.</li>
            <li>No Mac, pegue o IP: <code className="bg-edge px-1 rounded">tailscale ip -4</code> → <code className="bg-edge px-1 rounded">100.x.y.z</code>.</li>
            <li>Esse IP já está na <b>URL RTMP</b> acima.</li>
            <li>No celular, <b>mantenha o Tailscale ligado</b>: com o WiFi preso no drone, ele roteia o <code className="bg-edge px-1 rounded">100.x</code> pelo 4G/5G.</li>
            <li>Só o <b>ingest (1935)</b> passa pela VPN; o player roda local no Mac. Sem mexer no roteador.</li>
          </ol>
        </details>
      }
      footerNote={<>
        v0.1 — transmissão/reprodução + gravação. A <b>gravação é re-encodada em CFR</b> (frame rate constante, alta qualidade) → reprodução <b>fluida</b> mesmo com jitter de rede. O gráfico mostra a vazão real. RTMP não é criptografado: use VPN/rede privada.
      </>}
    />
  );
}
