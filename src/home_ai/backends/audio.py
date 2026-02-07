from __future__ import annotations

import os
from typing import Callable, Protocol, Sequence

from home_ai.audio import play_audio, stop_audio


class AudioPlayer(Protocol):
    def play(
        self,
        wav: Sequence[float],
        sample_rate: int,
        speed: float = 1.0,
        cancel_check: Callable[[], bool] | None = None,
        heartbeat: Callable[[], None] | None = None,
    ) -> bool:
        ...

    def stop(self) -> None:
        ...


class FFPlayAudioPlayer:
    def play(
        self,
        wav: Sequence[float],
        sample_rate: int,
        speed: float = 1.0,
        cancel_check: Callable[[], bool] | None = None,
        heartbeat: Callable[[], None] | None = None,
    ) -> bool:
        return play_audio(wav, sample_rate, speed, cancel_check, heartbeat)

    def stop(self) -> None:
        stop_audio()


def create_audio_player() -> AudioPlayer:
    backend = os.environ.get("HOME_AI_AUDIO_BACKEND", "ffplay").lower()
    if backend == "ffplay":
        return FFPlayAudioPlayer()
    raise ValueError(f"Unsupported audio backend: {backend}")
