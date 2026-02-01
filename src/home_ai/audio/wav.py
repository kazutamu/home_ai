import wave
from typing import Sequence, Tuple

import numpy as np


def write_wav(path: str, audio: Sequence[float], sample_rate: int) -> None:
    audio_np = np.asarray(audio, dtype=np.float32)
    if audio_np.size == 0:
        pcm_bytes = b""
    else:
        audio_np = np.clip(audio_np, -1.0, 1.0)
        pcm_bytes = (audio_np * 32767).astype(np.int16).tobytes()
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)


def load_wav(path: str) -> Tuple[np.ndarray, int]:
    with wave.open(path, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sampwidth = wav_file.getsampwidth()
        frames = wav_file.readframes(wav_file.getnframes())
    if sampwidth != 2:
        msg = f"Unsupported sample width: {sampwidth}"
        raise ValueError(msg)
    audio = np.frombuffer(frames, dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels)[:, 0]
    audio_f32 = audio.astype(np.float32) / 32767.0
    return audio_f32, sample_rate
