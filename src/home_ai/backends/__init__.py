from __future__ import annotations

from home_ai.backends.audio import AudioPlayer, create_audio_player
from home_ai.backends.llm import LLMClient, create_llm_client, get_default_llm_model
from home_ai.backends.tts import TTSEngine, create_tts_engine

__all__ = [
    "AudioPlayer",
    "LLMClient",
    "TTSEngine",
    "create_audio_player",
    "create_llm_client",
    "create_tts_engine",
    "get_default_llm_model",
    "get_audio_player",
    "get_llm_client",
    "get_tts_engine",
]

_LLM_CLIENT: LLMClient | None = None
_TTS_ENGINE: TTSEngine | None = None
_AUDIO_PLAYER: AudioPlayer | None = None


def get_llm_client() -> LLMClient:
    global _LLM_CLIENT
    if _LLM_CLIENT is None:
        _LLM_CLIENT = create_llm_client()
    return _LLM_CLIENT


def get_tts_engine() -> TTSEngine:
    global _TTS_ENGINE
    if _TTS_ENGINE is None:
        _TTS_ENGINE = create_tts_engine()
    return _TTS_ENGINE


def get_audio_player() -> AudioPlayer:
    global _AUDIO_PLAYER
    if _AUDIO_PLAYER is None:
        _AUDIO_PLAYER = create_audio_player()
    return _AUDIO_PLAYER
