from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Sequence
from typing import Optional

import numpy as np

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
        self._stream_epoch = 0
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

    def interrupt(self) -> int:
        loop = self._loop
        with self._clients_lock:
            self._stream_epoch += 1
            epoch = self._stream_epoch
            clients = list(self._clients)
        if loop is None or not clients:
            return epoch

        def _flush() -> None:
            for queue in clients:
                while True:
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

        loop.call_soon_threadsafe(_flush)
        return epoch

    def publish(self, data: bytes, *, stream_epoch: int | None = None) -> None:
        loop = self._loop
        if loop is None:
            return
        with self._clients_lock:
            current_epoch = self._stream_epoch
            clients = list(self._clients)
        if stream_epoch is not None and stream_epoch != current_epoch:
            return
        if not clients:
            return

        def _publish() -> None:
            with self._clients_lock:
                latest_epoch = self._stream_epoch
            if stream_epoch is not None and stream_epoch != latest_epoch:
                return
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


def stream_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/octet-stream",
        "Cache-Control": "no-store",
        "X-Audio-Format": "pcm_s16le",
        "X-Audio-Sample-Rate": str(BROADCASTER.sample_rate),
        "X-Audio-Channels": "1",
    }


async def stream_generator() -> AsyncIterator[bytes]:
    queue = BROADCASTER.register()
    print("[audio_stream] Client connected")
    try:
        await BROADCASTER.wait_for_format()
        while True:
            data = await queue.get()
            if data is None:
                break
            yield data
    except asyncio.CancelledError:
        raise
    finally:
        BROADCASTER.unregister(queue)
        print("[audio_stream] Client disconnected")
