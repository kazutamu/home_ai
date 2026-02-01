import shutil
import subprocess
import threading
import time
from typing import Callable, Optional, Sequence

import numpy as np

_CURRENT_PROC: Optional[subprocess.Popen] = None
_CURRENT_LOCK = threading.Lock()
FADE_OUT_SEC = 0.04
HEARTBEAT_INTERVAL_SEC = 1.0


def play_audio(
    wav: Sequence[float],
    sample_rate: int,
    speed: float = 1.0,
    cancel_check: Callable[[], bool] | None = None,
    heartbeat: Callable[[], None] | None = None,
) -> bool:
    """Play a waveform in-memory using ffplay for instant cancellation."""
    global _CURRENT_PROC
    if shutil.which("ffplay") is None:
        msg = "ffplay is required to play audio without saving a file."
        raise RuntimeError(msg)

    audio = _prepare_audio(wav, sample_rate, speed)
    pcm_bytes = _to_pcm_bytes(audio)

    cancelled = False
    chunk_size = 4096
    last_heartbeat = time.monotonic()

    cmd = [
        "ffplay",
        "-autoexit",
        "-nodisp",
        "-f",
        "s16le",
        "-ar",
        str(sample_rate),
        "-",
        "-af",
        f"atempo={speed}",
    ]
    with subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ) as proc:
        with _CURRENT_LOCK:
            _CURRENT_PROC = proc

        try:
            cancelled = _stream_audio(
                proc,
                pcm_bytes,
                chunk_size,
                cancel_check,
                heartbeat,
                last_heartbeat,
            )
        finally:
            with _CURRENT_LOCK:
                if _CURRENT_PROC is proc:
                    _CURRENT_PROC = None

    return cancelled


def stop_audio() -> None:
    """Stop current ffplay process if one is active."""
    with _CURRENT_LOCK:
        proc = _CURRENT_PROC
    if proc is None:
        return
    try:
        proc.kill()
    except Exception:
        pass


def _prepare_audio(wav: Sequence[float], sample_rate: int, speed: float) -> np.ndarray:
    audio = np.asarray(wav, dtype=np.float32)
    if speed != 1.0:
        new_len = max(1, int(len(audio) / speed))
        xp = np.linspace(0.0, 1.0, len(audio), endpoint=False)
        xq = np.linspace(0.0, 1.0, new_len, endpoint=False)
        audio = np.interp(xq, xp, audio).astype(np.float32)

    audio = np.clip(audio, -1.0, 1.0)
    fade_len = max(0, min(len(audio), int(sample_rate * FADE_OUT_SEC)))
    if fade_len:
        fade = np.linspace(1.0, 0.0, fade_len, endpoint=True, dtype=np.float32)
        audio[-fade_len:] *= fade
    return audio


def _to_pcm_bytes(audio: np.ndarray) -> bytes:
    return (audio * 32767).astype(np.int16).tobytes()


def _stream_audio(
    proc: subprocess.Popen,
    pcm_bytes: bytes,
    chunk_size: int,
    cancel_check: Callable[[], bool] | None,
    heartbeat: Callable[[], None] | None,
    last_heartbeat: float,
) -> bool:
    cancelled = False
    assert proc.stdin is not None
    view = memoryview(pcm_bytes)
    idx = 0
    while idx < len(view):
        if _should_cancel(cancel_check):
            cancelled = True
            proc.kill()
            break
        end = min(idx + chunk_size, len(view))
        try:
            proc.stdin.write(view[idx:end])
        except (BrokenPipeError, ValueError):
            cancelled = True
            break
        idx = end
        last_heartbeat = _maybe_heartbeat(heartbeat, last_heartbeat)

    _safe_close(proc.stdin)

    while proc.poll() is None:
        if _should_cancel(cancel_check):
            cancelled = True
            proc.kill()
            break
        last_heartbeat = _maybe_heartbeat(heartbeat, last_heartbeat)
        time.sleep(0.01)

    if cancelled:
        try:
            proc.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            proc.kill()

    return cancelled


def _should_cancel(cancel_check: Callable[[], bool] | None) -> bool:
    return cancel_check is not None and cancel_check()


def _maybe_heartbeat(
    heartbeat: Callable[[], None] | None, last_heartbeat: float
) -> float:
    if heartbeat is None:
        return last_heartbeat
    now = time.monotonic()
    if now - last_heartbeat >= HEARTBEAT_INTERVAL_SEC:
        heartbeat()
        return now
    return last_heartbeat


def _safe_close(handle: Optional[object]) -> None:
    if handle is None:
        return
    try:
        handle.close()
    except Exception:
        pass
