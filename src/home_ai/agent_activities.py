import asyncio
import threading

from temporalio import activity
from temporalio.exceptions import CancelledError

from .audio import play_audio, stop_audio
from .chatbot import reply
from .models import TextToSpeech

PLAYBACK_SPEED = 1.25


async def _run_with_cancel(task: asyncio.Task):
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=0.1)
            if done:
                return task.result()
            if activity.is_cancelled():
                task.cancel()
                raise CancelledError()
            activity.heartbeat()
    finally:
        if not task.done():
            task.cancel()


@activity.defn(name="llm_respond")
async def llm_respond(text: str) -> str:
    if activity.is_cancelled():
        raise CancelledError()
    task = asyncio.create_task(asyncio.to_thread(reply, text))
    return await _run_with_cancel(task)


@activity.defn(name="speak_text")
async def speak_text(text: str) -> None:
    """Synth + play inside the activity to avoid returning large payloads."""
    if activity.is_cancelled():
        raise CancelledError()
    tts = TextToSpeech()
    synth_task = asyncio.create_task(asyncio.to_thread(tts.synthesize, text))
    audio, sample_rate = await _run_with_cancel(synth_task)

    if activity.is_cancelled():
        raise CancelledError()
    stop_event = threading.Event()
    playback_task = asyncio.create_task(
        asyncio.to_thread(
            play_audio,
            audio,
            sample_rate,
            PLAYBACK_SPEED,
            stop_event.is_set,
            None,
        )
    )
    try:
        while True:
            done, _ = await asyncio.wait({playback_task}, timeout=0.1)
            if done:
                cancelled = playback_task.result()
                if cancelled:
                    raise CancelledError()
                return
            if activity.is_cancelled():
                stop_event.set()
                try:
                    await playback_task
                finally:
                    raise CancelledError()
            activity.heartbeat()
    finally:
        if not playback_task.done():
            stop_event.set()


@activity.defn(name="stop_audio")
async def stop_audio_activity() -> None:
    stop_audio()
