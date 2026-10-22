"""Helpers de descoberta de câmeras (funções puras, sem acesso à rede)."""
from __future__ import annotations

from app.discovery import netscan
from app.discovery.onvif_ws import _scope_value


def test_is_private():
    assert netscan.is_private("192.168.1.64") is True
    assert netscan.is_private("10.1.2.3") is True
    assert netscan.is_private("172.16.5.5") is True
    assert netscan.is_private("8.8.8.8") is False
    assert netscan.is_private("não-ip") is False


def test_subnet_hosts_count():
    hosts = netscan.subnet_hosts("192.168.1.10", 24)
    assert len(hosts) == 254
    assert "192.168.1.1" in hosts and "192.168.1.254" in hosts


def test_rtsp_candidates():
    cands = netscan.rtsp_candidates("192.168.1.64", [80, 554, 34567])
    assert all(c.startswith("rtsp://192.168.1.64:554") for c in cands)
    assert any("/onvif1" in c for c in cands)
    assert any("realmonitor" in c for c in cands)  # Dahua
    assert any("stream=0.sdp" in c for c in cands)  # Xiongmai/ICSee


def test_onvif_scope_value():
    scopes = [
        "onvif://www.onvif.org/name/Camera%20Patio",
        "onvif://www.onvif.org/hardware/X3-WQ-B",
    ]
    assert _scope_value(scopes, "name") == "Camera Patio"
    assert _scope_value(scopes, "hardware") == "X3-WQ-B"
    assert _scope_value(scopes, "location") is None
