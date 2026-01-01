import queue
from typing import List

import numpy as np
import sounddevice as sd
from sounddevice import PortAudioError

from ..config import SAMPLE_RATE


def record_until_enter(samplerate: int = SAMPLE_RATE, channels: int = 1) -> np.ndarray:
    """Record audio until Enter is pressed and return a flattened float32 waveform."""
    q: queue.Queue[np.ndarray] = queue.Queue()

    def callback(indata, frames, time, status):
        if status:
            print(status)
        q.put(indata.copy())

    print("Recording... press Enter to stop.")
    try:
        with sd.InputStream(samplerate=samplerate, channels=channels, callback=callback):
            input()
    except PortAudioError as exc:
        msg = (
            f"Could not open input device: {exc}. "
            "Check that your microphone is available to the container or select a valid device."
        )
        raise RuntimeError(msg) from exc
    chunks: List[np.ndarray] = []
    while not q.empty():
        chunks.append(q.get())
    if not chunks:
        return np.array([], dtype=np.float32)
    return np.concatenate(chunks, axis=0).flatten()
