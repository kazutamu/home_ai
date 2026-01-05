"""
Activities run outside the Temporal workflow sandbox, so network calls (e.g. Ollama)
and other side effects belong here.
"""

from typing import List, Tuple

import numpy as np
from temporalio import activity

from .audio import play_audio as play_audio_out
from .chatbot import reply
from .models import TextToSpeech
from .config import PLAYBACK_SPEED


@activity.defn(name="llm_respond")
async def llm_respond(text: str) -> str:
    return reply(text)


@activity.defn(name="text_to_speech")
async def text_to_speech(text: str) -> Tuple[list, int]:
    tts = TextToSpeech()
    return tts.synthesize(text)


@activity.defn(name="play_audio")
async def play_audio(audio: list, sample_rate: int) -> None:
    play_audio_out(audio, sample_rate, speed=PLAYBACK_SPEED)
