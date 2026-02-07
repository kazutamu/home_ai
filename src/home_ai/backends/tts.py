from __future__ import annotations

import os
from typing import Protocol

from home_ai.models import TextToSpeech


class TTSEngine(Protocol):
    def synthesize(self, text: str) -> tuple[list[float], int]:
        ...


def create_tts_engine() -> TTSEngine:
    backend = os.environ.get("HOME_AI_TTS_BACKEND", "coqui").lower()
    if backend == "coqui":
        return TextToSpeech()
    raise ValueError(f"Unsupported TTS backend: {backend}")
