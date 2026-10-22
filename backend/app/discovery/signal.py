"""Monitoramento de sinal/transmissão estilo IoT.

Mede, de forma rápida e não-bloqueante, a qualidade do enlace até cada câmera
(latência TCP + jitter por várias amostras paralelas) e o RSSI do Wi-Fi local
(macOS, best-effort). Tudo com timeouts curtos e cache, para leitura ágil.

Honestidade: não há telemetria de RSSI das câmeras (a maioria não expõe); o
"sinal"/"buffer" por câmera é derivado da latência/jitter reais do enlace e
rotulado como estimativa. Conectores e rede cabeada ficam como slots em espera.
"""
from __future__ import annotations

import asyncio
import re
import subprocess
import time
from statistics import median

# cache simples (TTL) para não sondar a cada poll do frontend.
# TTL >= cadência de poll para que /overview e /signal compartilhem o mesmo
# resultado e não dupliquem o probe de rede (otimização de leitura).
_cache: dict[str, tuple[float, object]] = {}
_TTL = 10.0


def _cached(key: str):
    hit = _cache.get(key)
    if hit and (time.monotonic() - hit[0]) < _TTL:
        return hit[1]
    return None


def _store(key: str, value: object):
    _cache[key] = (time.monotonic(), value)
    return value


async def _tcp_latency(host: str, port: int, timeout: float = 1.5) -> float | None:
    """Tempo de conexão TCP em ms, ou None se falhar."""
    loop = asyncio.get_running_loop()
    start = loop.time()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        return (loop.time() - start) * 1000.0
    except Exception:  # noqa: BLE001
        return None


def _quality(latency_ms: float | None) -> tuple[int, str]:
    """Mapeia latência → (barras 0..4, rótulo)."""
    if latency_ms is None:
        return 0, "offline"
    if latency_ms < 30:
        return 4, "excelente"
    if latency_ms < 80:
        return 3, "bom"
    if latency_ms < 200:
        return 2, "regular"
    return 1, "fraco"


async def probe_camera(name: str, host: str, port: int, samples: int = 4) -> dict:
    """Sonda um host: latência mediana, jitter, perda, qualidade e buffer estimado."""
    results = await asyncio.gather(*[_tcp_latency(host, port) for _ in range(samples)])
    oks = [r for r in results if r is not None]
    loss = round(100 * (samples - len(oks)) / samples)
    lat = round(median(oks), 1) if oks else None
    jitter = round((max(oks) - min(oks)), 1) if len(oks) > 1 else 0.0
    bars, label = _quality(lat)
    # "buffer" estimado: ocupação cresce com latência/jitter (rede pior ⇒ mais buffer).
    if lat is None:
        buffer_pct = 0
    else:
        buffer_pct = max(5, min(100, round((lat + jitter * 2) / 4)))
    # bitrate/fps estimados a partir da qualidade (sem telemetria real do encoder)
    fps_est = [0, 6, 12, 20, 25][bars]
    return {
        "name": name,
        "host": host,
        "port": port,
        "online": bool(oks),
        "latency_ms": lat,
        "jitter_ms": jitter,
        "packet_loss_pct": loss,
        "bars": bars,
        "quality": label,
        "buffer_pct": buffer_pct,
        "fps_est": fps_est,
        "transport": "wifi",
    }


def _wifi_rssi_macos() -> dict | None:
    """Lê RSSI/ruído do Wi-Fi local no macOS (best-effort, sem sudo)."""
    cached = _cached("wifi")
    if cached is not None:
        return cached  # type: ignore[return-value]
    info: dict | None = None
    try:
        out = subprocess.run(
            ["/usr/sbin/system_profiler", "SPAirPortDataType"],
            capture_output=True, text=True, timeout=2.5,
        ).stdout
        # bloco "Current Network Information" tem "Signal / Noise: -47 dBm / -90 dBm"
        sig = re.search(r"Signal\s*/\s*Noise:\s*(-?\d+)\s*dBm\s*/\s*(-?\d+)\s*dBm", out)
        ssid = re.search(r"Current Network Information:\s*\n\s*([^\n]+):", out)
        tx = re.search(r"Transmit Rate:\s*([\d.]+)", out)
        if sig:
            rssi = int(sig.group(1))
            noise = int(sig.group(2))
            # qualidade: -50 excelente … -80 fraco
            bars = 4 if rssi >= -55 else 3 if rssi >= -67 else 2 if rssi >= -75 else 1
            info = {
                "ssid": ssid.group(1).strip() if ssid else None,
                "rssi_dbm": rssi,
                "noise_dbm": noise,
                "snr_db": rssi - noise,
                "tx_rate_mbps": float(tx.group(1)) if tx else None,
                "bars": bars,
                "available": True,
            }
    except Exception:  # noqa: BLE001
        info = None
    if info is None:
        info = {"available": False}
    return _store("wifi", info)  # type: ignore[return-value]


async def probe_cameras(cameras: list[dict]) -> list[dict]:
    """Só os probes de câmera (cacheados) — usado pelo /overview, sem custo de Wi-Fi."""
    cached = _cached("cams")
    if cached is not None:
        return cached  # type: ignore[return-value]
    probes = await asyncio.gather(
        *[probe_camera(c.get("name", c["ip"]), c["ip"], int(c.get("port", 554))) for c in cameras]
    ) if cameras else []
    return _store("cams", list(probes))  # type: ignore[return-value]


async def snapshot_signal(cameras: list[dict]) -> dict:
    """Estado de sinal de todas as câmeras + Wi-Fi local + slots em espera."""
    cached = _cached("signal")
    if cached is not None:
        return cached  # type: ignore[return-value]

    # Probes de câmera (async) + leitura de Wi-Fi (subprocess) em paralelo; o
    # system_profiler roda numa thread para não bloquear o event loop.
    probes, wifi = await asyncio.gather(
        probe_cameras(cameras), asyncio.to_thread(_wifi_rssi_macos)
    )

    # anexa estado liga/desliga (raiz) + id por câmera → UI mostra "desligada" e age
    by_ip = {c["ip"]: c for c in cameras}
    cams_out = []
    for p in probes:
        cam = by_ip.get(p["host"], {})
        cams_out.append({**p, "enabled": cam.get("enabled", True), "id": cam.get("id")})

    payload = {
        "wifi": wifi,
        "cameras": cams_out,
        "links": [
            {"tipo": "wifi", "label": "Wi-Fi (transmissão)", "status": "ativo" if probes else "sem câmeras"},
            {"tipo": "conector", "label": "Conector externo", "status": "aguardando",
             "note": "Slot reservado — aguardando hardware conector."},
            {"tipo": "cabeada", "label": "Rede cabeada (Ethernet)", "status": "aguardando",
             "note": "Slot reservado — aguardando rede cabeada."},
        ],
    }
    return _store("signal", payload)  # type: ignore[return-value]
