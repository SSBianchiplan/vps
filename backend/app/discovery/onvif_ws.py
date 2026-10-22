"""ONVIF WS-Discovery: descobre câmeras compatíveis via multicast UDP.

Envia um Probe SOAP para 239.255.255.250:3702 e coleta as respostas com os
endereços de serviço (XAddrs) e escopos (nome/hardware). Puro Python (socket).
"""
from __future__ import annotations

import asyncio
import re
import socket
import uuid

_MCAST = ("239.255.255.250", 3702)

_PROBE = """<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
 xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
 xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
 <e:Header>
  <w:MessageID>uuid:{mid}</w:MessageID>
  <w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
  <w:Action e:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
 </e:Header>
 <e:Body>
  <d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe>
 </e:Body>
</e:Envelope>"""


def _scope_value(scopes: list[str], key: str) -> str | None:
    # ex.: onvif://www.onvif.org/name/MinhaCam → "MinhaCam"
    for s in scopes:
        idx = s.find(f"/{key}/")
        if idx != -1:
            val = s[idx + len(key) + 2 :].split("/")[0]
            return val.replace("%20", " ") or None
    return None


async def discover(timeout: float = 3.0) -> list[dict]:
    """Lista dispositivos ONVIF: [{ip, xaddrs, scopes, name, hardware}]."""
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.bind(("", 0))
    sock.setblocking(False)

    msg = _PROBE.format(mid=uuid.uuid4()).encode()
    found: dict[str, dict] = {}
    try:
        sock.sendto(msg, _MCAST)
        end = loop.time() + timeout
        while True:
            remaining = end - loop.time()
            if remaining <= 0:
                break
            try:
                data, addr = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 65535), timeout=remaining
                )
            except asyncio.TimeoutError:
                break
            except Exception:
                break
            text = data.decode(errors="ignore")
            xaddrs = " ".join(re.findall(r"XAddrs>([^<]+)<", text)).split()
            scope_match = re.findall(r"Scopes[^>]*>([^<]+)<", text)
            scopes = scope_match[0].split() if scope_match else []
            ip = addr[0]
            entry = found.setdefault(
                ip, {"ip": ip, "xaddrs": [], "scopes": [], "name": None, "hardware": None}
            )
            entry["xaddrs"] = sorted(set(entry["xaddrs"]) | set(xaddrs))
            if scopes:
                entry["scopes"] = scopes
                entry["name"] = _scope_value(scopes, "name") or entry["name"]
                entry["hardware"] = _scope_value(scopes, "hardware") or entry["hardware"]
    finally:
        sock.close()
    return list(found.values())
