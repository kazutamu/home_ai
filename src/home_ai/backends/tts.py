from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from home_ai.models import TextToSpeech


class TTSEngine(Protocol):
    def synthesize(self, text: str) -> tuple[list[float], int]:
        ...


@dataclass
class GoogleTTSEngine:
    language_code: str = "en-US"
    voice_name: str | None = None
    sample_rate_hz: int = 24000

    def __post_init__(self) -> None:
        from google.cloud import texttospeech

        self._texttospeech = texttospeech
        self._client = texttospeech.TextToSpeechClient()

    def synthesize(self, text: str) -> tuple[list[float], int]:
        if not text:
            return [], self.sample_rate_hz
        input_text = self._texttospeech.SynthesisInput(text=text)
        voice = self._texttospeech.VoiceSelectionParams(
            language_code=self.language_code,
            name=self.voice_name or None,
        )
        audio_config = self._texttospeech.AudioConfig(
            audio_encoding=self._texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.sample_rate_hz,
        )
        response = self._client.synthesize_speech(
            input=input_text, voice=voice, audio_config=audio_config
        )
        audio_i16 = np.frombuffer(response.audio_content, dtype=np.int16)
        audio_f32 = (audio_i16.astype(np.float32) / 32768.0).tolist()
        return audio_f32, int(self.sample_rate_hz)


def create_tts_engine() -> TTSEngine:
    backend = os.environ.get("HOME_AI_TTS_BACKEND", "coqui").lower()
    if backend == "coqui":
        return TextToSpeech()
    if backend == "google":
        language_code = os.environ.get("HOME_AI_TTS_GOOGLE_LANGUAGE", "en-US")
        voice_name = os.environ.get("HOME_AI_TTS_GOOGLE_VOICE") or None
        sample_rate_hz = int(os.environ.get("HOME_AI_TTS_GOOGLE_SAMPLE_RATE", "24000"))
        return GoogleTTSEngine(
            language_code=language_code,
            voice_name=voice_name,
            sample_rate_hz=sample_rate_hz,
        )
    raise ValueError(f"Unsupported TTS backend: {backend}")
