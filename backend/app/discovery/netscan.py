"""Varredura de portas no /24 local para encontrar câmeras IP.

Restrito a faixas privadas (RFC1918) por segurança — nunca varre IPs públicos.
Usa conexões TCP assíncronas com timeout curto e alta concorrência.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket

# Portas típicas de câmeras IP:
# 554/8554 RTSP · 80/8080/88 HTTP/ONVIF · 8000 ONVIF (Hik) · 37777 Dahua · 34567 Xiongmai/ICSee
COMMON_PORTS: list[int] = [554, 8554, 80, 8080, 88, 8000, 37777, 34567]

_PRIVATE = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]


def local_ipv4() -> str | None:
    """IP local da interface ativa (sem enviar pacotes — só resolve a rota)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def is_private(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in _PRIVATE)


def subnet_hosts(ip: str, prefix: int = 24) -> list[str]:
    net = ipaddress.ip_interface(f"{ip}/{prefix}").network
    return [str(h) for h in net.hosts()]


async def _port_open(ip: str, port: int, timeout: float) -> bool:
    try:
        fut = asyncio.open_connection(ip, port)
        _, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), timeout=0.2)
        except Exception:
            pass
        return True
    except Exception:
        return False


async def scan_ports(
    hosts: list[str],
    ports: list[int],
    timeout: float = 0.6,
    concurrency: int = 256,
) -> dict[str, list[int]]:
    """Devolve {ip: [portas abertas]} para os hosts varridos."""
    sem = asyncio.Semaphore(concurrency)
    results: dict[str, list[int]] = {}
    lock = asyncio.Lock()

    async def probe(ip: str, port: int) -> None:
        async with sem:
            if await _port_open(ip, port, timeout):
                async with lock:
                    results.setdefault(ip, []).append(port)

    await asyncio.gather(*(probe(ip, p) for ip in hosts for p in ports))
    for ip in results:
        results[ip].sort()
    return results


def rtsp_candidates(ip: str, ports: list[int]) -> list[str]:
    """URLs RTSP candidatas (sem credenciais) cobrindo as famílias comuns."""
    port = 554 if 554 in ports or not ports else (8554 if 8554 in ports else 554)
    base = f"rtsp://{ip}:{port}"
    paths = [
        "/onvif1",                                  # ONVIF genérico (perfil 1)
        "/onvif2",                                  # ONVIF genérico (substream)
        "/Streaming/Channels/101",                  # Hikvision (main)
        "/Streaming/Channels/102",                  # Hikvision (sub)
        "/cam/realmonitor?channel=1&subtype=0",     # Dahua (main)
        "/cam/realmonitor?channel=1&subtype=1",     # Dahua (sub)
        "/user=admin&password=&channel=1&stream=0.sdp",  # Xiongmai/ICSee (main)
        "/user=admin&password=&channel=1&stream=1.sdp",  # Xiongmai/ICSee (sub)
        "/live/ch0",                                # genérico
        "/11",                                      # CamHi (main)
        "/12",                                      # CamHi (sub)
        "/h264Preview_01_main",                     # Reolink
    ]
    return [base + p for p in paths]
