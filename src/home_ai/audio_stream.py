from __future__ import annotations

import asyncio
import threading
from collections.abc import Sequence
from typing import Optional

import numpy as np
from aiohttp import web

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHUNK_SIZE = 4096


def float_to_pcm16(wav: Sequence[float]) -> bytes:
    audio = np.asarray(wav, dtype=np.float32)
    audio = np.clip(audio, -1.0, 1.0)
    return (audio * 32767).astype(np.int16).tobytes()


class AudioBroadcaster:
    def __init__(self) -> None:
        self._clients: set[asyncio.Queue[Optional[bytes]]] = set()
        self._clients_lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._sample_rate = DEFAULT_SAMPLE_RATE
        self._format_ready = asyncio.Event()

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def set_sample_rate(self, sample_rate: int) -> None:
        if sample_rate > 0:
            self._sample_rate = sample_rate
            loop = self._loop
            if loop is not None:
                loop.call_soon_threadsafe(self._format_ready.set)

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    async def wait_for_format(self) -> None:
        await self._format_ready.wait()

    def register(self) -> asyncio.Queue[Optional[bytes]]:
        queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue(maxsize=10)
        with self._clients_lock:
            self._clients.add(queue)
        return queue

    def unregister(self, queue: asyncio.Queue[Optional[bytes]]) -> None:
        with self._clients_lock:
            self._clients.discard(queue)

    def publish(self, data: bytes) -> None:
        loop = self._loop
        if loop is None:
            return
        with self._clients_lock:
            clients = list(self._clients)
        if not clients:
            return

        def _publish() -> None:
            for queue in clients:
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    queue.put_nowait(data)
                except asyncio.QueueFull:
                    pass

        loop.call_soon_threadsafe(_publish)


BROADCASTER = AudioBroadcaster()


async def _stream_handler(request: web.Request) -> web.StreamResponse:
    queue = BROADCASTER.register()
    peer = request.remote or "unknown"
    print(f"[audio_stream] Client connected: {peer}")
    await BROADCASTER.wait_for_format()
    headers = {
        "Content-Type": "application/octet-stream",
        "Cache-Control": "no-store",
        "X-Audio-Format": "pcm_s16le",
        "X-Audio-Sample-Rate": str(BROADCASTER.sample_rate),
        "X-Audio-Channels": "1",
    }
    response = web.StreamResponse(status=200, reason="OK", headers=headers)
    await response.prepare(request)
    try:
        while True:
            data = await queue.get()
            if data is None:
                break
            await response.write(data)
    except asyncio.CancelledError:
        raise
    except Exception:
        pass
    finally:
        BROADCASTER.unregister(queue)
        print(f"[audio_stream] Client disconnected: {peer}")
    return response


async def start_audio_stream_server(host: str, port: int) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/audio/stream", _stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"Audio stream server listening on http://{host}:{port}/audio/stream")
    return runner
