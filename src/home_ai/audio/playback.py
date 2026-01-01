import shutil
import subprocess
from typing import Sequence

import numpy as np


def play_audio(wav: Sequence[float], sample_rate: int, speed: float = 1.0) -> None:
    """Play a waveform in-memory using ffplay so we don't write to disk."""
    if shutil.which("ffplay") is None:
        msg = "ffplay is required to play audio without saving a file."
        raise RuntimeError(msg)

    audio = np.clip(np.asarray(wav), -1.0, 1.0)
    pcm_bytes = (audio * 32767).astype(np.int16).tobytes()

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
        assert proc.stdin is not None
        proc.stdin.write(pcm_bytes)
        proc.stdin.close()
        proc.wait()
