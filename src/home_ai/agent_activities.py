import asyncio
import threading

from temporalio import activity
from temporalio.exceptions import CancelledError

from .audio import play_audio, stop_audio
from .chatbot import reply
from .models import TextToSpeech

PLAYBACK_SPEED = 1.25


async def _wait_with_heartbeat(task: asyncio.Task, *, on_cancel):
    while True:
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=0.1)
        except asyncio.TimeoutError:
            if activity.is_cancelled():
                await on_cancel()
        activity.heartbeat()


async def _run_task(task: asyncio.Task, *, on_cancel, cancel_on_exit: bool = True):
    try:
        return await _wait_with_heartbeat(task, on_cancel=on_cancel)
    finally:
        if cancel_on_exit and not task.done():
            task.cancel()


async def _run_task_with_stop(task: asyncio.Task, stop_callback):
    async def _handle_cancel() -> None:
        stop_callback()
        try:
            await task
        finally:
            raise CancelledError()

    return await _run_task(task, on_cancel=_handle_cancel, cancel_on_exit=False)


async def _run_task_with_cancel(task: asyncio.Task):
    async def _handle_cancel() -> None:
        if not task.done():
            task.cancel()
        raise CancelledError()

    return await _run_task(task, on_cancel=_handle_cancel)


@activity.defn(name="llm_respond")
async def llm_respond(text: str) -> str:
    task = asyncio.create_task(asyncio.to_thread(reply, text))
    return await _run_task_with_cancel(task)


@activity.defn(name="speak_text")
async def speak_text(text: str) -> None:
    """Synth + play inside the activity to avoid returning large payloads."""
    tts = TextToSpeech()
    synth_task = asyncio.create_task(asyncio.to_thread(tts.synthesize, text))
    audio, sample_rate = await _run_task_with_cancel(synth_task)

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
        await _run_task_with_stop(playback_task, stop_event.set)
    finally:
        if not playback_task.done():
            stop_event.set()


@activity.defn(name="stop_audio")
async def stop_audio_activity() -> None:
    stop_audio()
