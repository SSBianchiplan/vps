"""Streaming RTSP→MJPEG de baixa latência.

Por câmera, mantém UMA captura OpenCV numa thread que drena o buffer e guarda
só o frame mais recente (sempre "ao vivo", sem acúmulo). Clientes consomem via
multipart/x-mixed-replace. Captura inicia no 1º cliente e para após ociosidade.
"""
from __future__ import annotations

import asyncio
import os
import threading
import time
from typing import Any

# Baixa latência no FFmpeg do OpenCV: TCP, sem buffer, baixo atraso.
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;500000|stimeout;6000000"
)

from .snapshot import _cv2, _open_capture  # noqa: E402  (reaproveita setup OpenCV)

_MAX_W = 1280          # default leve (painel); o Estúdio pede mais via captureWidth (max_w)
_JPEG_Q = 85           # qualidade JPEG (nitidez p/ OCR/análise); equilíbrio tamanho×detalhe
_IDLE_S = 12.0          # para a captura após N s sem clientes
_RECONNECT_S = 1.0


class _Stream:
    def __init__(self, urls: list[str], key: str, max_w: int = _MAX_W, quality: int = _JPEG_Q, start: bool = True) -> None:
        self.urls = urls            # tenta em ordem (substream → main) c/ fallback
        self.key = key
        self.idx = 0
        self.max_w = max_w          # largura-alvo (0 = nativa, sem reduzir)
        self.quality = quality      # qualidade JPEG (1–100)
        self.jpeg: bytes | None = None
        self.seq = 0
        self.total_bytes = 0          # cumulativo p/ medir vazão (monitoramento)
        self.clients = 0
        self.run = start            # start=False → stream "morto" (câmera desligada): não captura, não conta vazão
        self.err: str | None = None
        self.cond = threading.Condition()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        if start:
            self.thread.start()

    def _publish(self, jpeg: bytes) -> None:
        with self.cond:
            self.jpeg = jpeg
            self.seq += 1
            self.total_bytes += len(jpeg)
            self.err = None
            self.cond.notify_all()

    def _loop(self) -> None:
        cv2 = _cv2()
        if cv2 is None:
            with self.cond:
                self.err = "OpenCV indisponível"
                self.cond.notify_all()
            return
        cap = None
        fails = 0
        idle_since = time.monotonic()
        while self.run:
            if self.clients == 0:
                if time.monotonic() - idle_since > _IDLE_S:
                    if _manager.reap(self):   # decisão sob lock evita corrida c/ acquire()
                        break
                    idle_since = time.monotonic()  # cliente chegou no intervalo — segue
                    continue
                time.sleep(0.2)
                continue
            idle_since = time.monotonic()
            if cap is None or not cap.isOpened():
                cap = _open_capture(cv2, self.urls[self.idx])
                if not cap.isOpened():
                    cap = None; fails += 1
                    if fails >= 2 and len(self.urls) > 1:  # tenta próxima URL (fallback)
                        self.idx = (self.idx + 1) % len(self.urls); fails = 0
                    with self.cond:
                        self.err = "sem conexão RTSP"; self.cond.notify_all()
                    time.sleep(_RECONNECT_S)
                    continue
                fails = 0
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.release(); cap = None; fails += 1
                if fails >= 3 and len(self.urls) > 1:
                    self.idx = (self.idx + 1) % len(self.urls); fails = 0
                time.sleep(_RECONNECT_S)
                continue
            h, w = frame.shape[:2]
            mw = self.max_w
            if mw and w > mw:
                frame = cv2.resize(frame, (mw, int(h * mw / w)))
            ok2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
            if ok2:
                self._publish(bytes(buf))
        if cap is not None:
            cap.release()

    def wait(self, last_seq: int, timeout: float = 5.0) -> tuple[bytes | None, int]:
        with self.cond:
            self.cond.wait_for(lambda: self.seq != last_seq or not self.run, timeout=timeout)
            return self.jpeg, self.seq


class _Manager:
    def __init__(self) -> None:
        self._streams: dict[str, _Stream] = {}
        self._blocked: set[str] = set()   # tokens (ex.: IP) de câmeras desligadas → não streamam
        self._lock = threading.Lock()

    def acquire(self, urls: list[str], max_w: int | None = None, quality: int | None = None) -> _Stream:
        key = urls[0]
        with self._lock:
            if any(tok in key for tok in self._blocked):
                # câmera desligada (raiz): devolve stream morto (não captura, não conta vazão)
                return _Stream(urls, key, _MAX_W, _JPEG_Q, start=False)
            s = self._streams.get(key)
            if s is None or not s.thread.is_alive():
                s = _Stream(urls, key, max_w if max_w is not None else _MAX_W, quality or _JPEG_Q)
                self._streams[key] = s
            else:
                # reusa o stream existente, ajustando resolução/qualidade ao vivo (sem reconectar)
                if max_w is not None:
                    s.max_w = max_w
                if quality:
                    s.quality = quality
            s.clients += 1
            return s

    def release(self, key: str) -> None:
        with self._lock:
            s = self._streams.get(key)
            if s:
                s.clients = max(0, s.clients - 1)

    def reap(self, stream: _Stream) -> bool:
        """Sob lock: se sem clientes, remove do dict e autoriza o loop a parar."""
        with self._lock:
            if stream.clients == 0 and self._streams.get(stream.key) is stream:
                self._streams.pop(stream.key, None)
                stream.run = False
                return True
            return False

    def block(self, token: str) -> None:
        """Desliga a câmera (token = IP): derruba o stream RTSP vivo e impede recriação."""
        with self._lock:
            self._blocked.add(token)
            for key, s in list(self._streams.items()):
                if token in key:
                    s.run = False
                    self._streams.pop(key, None)
                    with s.cond:
                        s.cond.notify_all()   # acorda mjpeg/latest p/ encerrarem já

    def unblock(self, token: str) -> None:
        with self._lock:
            self._blocked.discard(token)

    def sync_blocked(self, tokens: list[str]) -> None:
        """Define o conjunto exato de tokens bloqueados (sync com a raiz no startup)."""
        with self._lock:
            self._blocked = set(tokens)
            for key, s in list(self._streams.items()):
                if any(t in key for t in self._blocked):
                    s.run = False
                    self._streams.pop(key, None)
                    with s.cond:
                        s.cond.notify_all()


_manager = _Manager()
_BOUNDARY = "frame"


def block(token: str) -> None:
    _manager.block(token)


def unblock(token: str) -> None:
    _manager.unblock(token)


def sync_blocked(tokens: list[str]) -> None:
    _manager.sync_blocked(tokens)


def stats() -> dict:
    """Vazão agregada dos streams de câmera ativos (monitoramento do Painel)."""
    with _manager._lock:  # noqa: SLF001 — leitura rápida sob o mesmo lock
        live = [s for s in _manager._streams.values() if s.thread.is_alive() and s.clients > 0]
        return {"streams": len(live), "bytes": sum(s.total_bytes for s in live)}


async def mjpeg(urls: list[str], fps_cap: float = 25.0, max_w: int | None = None, quality: int | None = None):
    """Gerador async de multipart MJPEG (um frame por vez, sempre o mais recente)."""
    s = _manager.acquire(urls, max_w, quality)
    last = -1
    min_dt = 1.0 / fps_cap
    try:
        while True:
            jpeg, seq = await asyncio.to_thread(s.wait, last, 5.0)
            if jpeg is None:
                if not s.thread.is_alive():
                    break
                continue
            last = seq
            yield (
                b"--" + _BOUNDARY.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"
            )
            await asyncio.sleep(min_dt)
    finally:
        _manager.release(urls[0])


async def latest_jpeg(urls: list[str], timeout: float = 6.0, max_w: int | None = None, quality: int | None = None) -> bytes | None:
    """Frame JPEG mais recente do stream compartilhado de baixa latência.

    Reusa a MESMA captura RTSP do preview MJPEG (1 conexão por câmera), devolve
    sempre um frame FRESCO já redimensionado (≤1280px) e comprimido (Q72) — ~20x
    menor que o full-res — sem reabrir conexão nem ler frame defasado do buffer.
    Usado pela inferência (snapshot) p/ acelerar a captação de câmeras IP.
    """
    s = _manager.acquire(urls, max_w, quality)
    try:
        start = s.seq

        def _read() -> bytes | None:
            with s.cond:
                s.cond.wait_for(lambda: s.seq != start or not s.run, timeout=timeout)
                return s.jpeg

        return await asyncio.to_thread(_read)
    finally:
        _manager.release(urls[0])


def substream_candidates(url: str) -> list[str]:
    """Deriva URL(s) de substream (baixa-res/H264) p/ menos latência; main como fallback."""
    subs: list[str] = []
    if "onvif1" in url:
        subs.append(url.replace("onvif1", "onvif2"))      # Xiongmai/iCSee
    if "subtype=0" in url:
        subs.append(url.replace("subtype=0", "subtype=1"))  # Dahua
    if "/cam/realmonitor" in url and "subtype=" not in url:
        sep = "&" if "?" in url else "?"
        subs.append(f"{url}{sep}subtype=1")
    subs.append(url)  # fallback: main
    # remove duplicatas preservando ordem
    seen: set[str] = set()
    return [u for u in subs if not (u in seen or seen.add(u))]


def content_type() -> str:
    return f"multipart/x-mixed-replace; boundary={_BOUNDARY}"
