"""
Activities run outside the Temporal workflow sandbox, so network calls (e.g. Ollama)
and other side effects belong here.
"""

import asyncio
from temporalio import activity


@activity.defn(name="llm_respond")
async def llm_respond(text: str) -> str:
    # TODO: replace this stub with a real Ollama call.
    await asyncio.sleep(4)
    return f"回答: {text}（の続き…）"


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
