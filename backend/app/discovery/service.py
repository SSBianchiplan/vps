"""Orquestra a descoberta: ONVIF WS-Discovery + varredura de portas do /24."""
from __future__ import annotations

from typing import Any

from . import netscan, onvif_ws

# Portas que indicam fortemente uma câmera/NVR.
_CAMERA_PORTS = {554, 8554, 8000, 37777, 34567, 88}


async def scan(
    timeout: float = 3.0,
    ports: list[int] | None = None,
    do_onvif: bool = True,
    do_portscan: bool = True,
) -> dict[str, Any]:
    local_ip = netscan.local_ipv4()
    cams: dict[str, dict] = {}

    # 1) ONVIF WS-Discovery (multicast)
    if do_onvif:
        try:
            for d in await onvif_ws.discover(timeout):
                c = cams.setdefault(
                    d["ip"], {"ip": d["ip"], "ports": [], "onvif": None, "rtsp_candidates": []}
                )
                c["onvif"] = {
                    "name": d.get("name"),
                    "hardware": d.get("hardware"),
                    "xaddrs": d.get("xaddrs", []),
                }
        except Exception:
            pass  # ambientes sem multicast não devem derrubar o scan

    # 2) Varredura de portas (somente sub-rede privada)
    subnet = None
    if do_portscan and local_ip and netscan.is_private(local_ip):
        subnet = f"{local_ip}/24"
        hosts = [h for h in netscan.subnet_hosts(local_ip) if h != local_ip]
        portmap = await netscan.scan_ports(hosts, ports or netscan.COMMON_PORTS)
        for host, plist in portmap.items():
            c = cams.setdefault(
                host, {"ip": host, "ports": [], "onvif": None, "rtsp_candidates": []}
            )
            c["ports"] = plist

    # 3) Pós-processamento: candidatos RTSP + flag de câmera provável
    for c in cams.values():
        c["likely_camera"] = bool(c["onvif"]) or any(p in _CAMERA_PORTS for p in c["ports"])
        if c["likely_camera"]:
            c["rtsp_candidates"] = netscan.rtsp_candidates(c["ip"], c["ports"])

    ordered = sorted(cams.values(), key=lambda x: (not x["likely_camera"], _ipkey(x["ip"])))
    return {
        "local_ip": local_ip,
        "subnet": subnet,
        "scanned_ports": ports or netscan.COMMON_PORTS,
        "cameras": ordered,
    }


def _ipkey(ip: str) -> tuple[int, ...]:
    try:
        return tuple(int(o) for o in ip.split("."))
    except Exception:
        return (999,)
