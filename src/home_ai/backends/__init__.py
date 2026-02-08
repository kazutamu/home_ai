from __future__ import annotations

from home_ai.backends.llm import LLMClient, create_llm_client, get_default_llm_model
from home_ai.backends.tts import TTSEngine, create_tts_engine

__all__ = [
    "LLMClient",
    "TTSEngine",
    "create_llm_client",
    "create_tts_engine",
    "get_default_llm_model",
    "get_llm_client",
    "get_tts_engine",
]

_LLM_CLIENT: LLMClient | None = None
_TTS_ENGINE: TTSEngine | None = None


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
