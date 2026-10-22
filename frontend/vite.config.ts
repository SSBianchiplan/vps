import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";

// HTTPS opcional: se ./certs/{key,cert}.pem existirem, serve em HTTPS.
// Necessário p/ getUserMedia (câmera do dispositivo) fora de localhost — ex. mobile via IP.
// VITE_HTTP=1 força HTTP puro (ideal p/ uso em http://localhost: contexto seguro, câmera OK, sem aviso de cert).
const KEY = "certs/key.pem", CERT = "certs/cert.pem";
const https = process.env.VITE_HTTP !== "1" && fs.existsSync(KEY) && fs.existsSync(CERT)
  ? { key: fs.readFileSync(KEY), cert: fs.readFileSync(CERT) }
  : undefined;

export default defineConfig({
  plugins: [react()],
  server: {
    // Sempre na 7777, acessível por localhost E pelo IP da rede (mobile).
    host: true,          // escuta em 0.0.0.0 → alcançável pelo IP local
    port: 7777,
    strictPort: true,    // falha em vez de trocar de porta silenciosamente
    https,               // HTTPS via certs (necessário p/ câmera fora de localhost)
    // Em dev, encaminha REST e WebSocket para o backend FastAPI (HTTP local).
    proxy: {
      "/api": {
        target: "http://localhost:8200",
        changeOrigin: true,
        // Não derruba o dev server se o backend cair/reiniciar (EPIPE/ECONNREFUSED).
        configure: (proxy) => proxy.on("error", () => undefined),
      },
      "/ws": {
        target: "ws://localhost:8200",
        ws: true,
        configure: (proxy) => proxy.on("error", () => undefined),
      },
    },
  },
});
