"""
Activities run outside the Temporal workflow sandbox, so network calls (e.g. Ollama)
and other side effects belong here.
"""

import asyncio
from temporalio import activity
from .chatbot import reply


@activity.defn(name="llm_respond")
async def llm_respond(text: str) -> str:
    return reply(text)


@activity.defn(name="text_to_speech")
async def text_to_speech(text: str) -> bytes:
    # TODO: call your TTS engine here.
    await asyncio.sleep(3)
    return text.encode("utf-8")


@activity.defn(name="play_audio")
async def play_audio(audio: bytes) -> None:
    # TODO: stream audio to your playback mechanism here.
    await asyncio.sleep(5)
    activity.logger.info("PLAY: %s", audio[:60])
