import asyncio
import contextlib
import os
import tempfile
import threading
from collections.abc import Callable

from temporalio import activity
from temporalio.exceptions import CancelledError

from .audio import load_wav, write_wav
from .backends import get_audio_player, get_tts_engine
from .chatbot import reply
from .notes.conversation_notes import append_session_summary_from_transcript
from .search.embedding_search import build_index, search_local_docs
from .workflow_utils import LLMRequest

DEFAULT_PLAYBACK_SPEED = 1.1


async def _wait_with_heartbeat(task: asyncio.Task, *, on_cancel):
    while True:
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=0.1)
        except asyncio.TimeoutError:
            if activity.is_cancelled():
                await on_cancel()
        activity.heartbeat()


async def _run_task(task: asyncio.Task, *, on_cancel=None):
    async def _default_cancel() -> None:
        if not task.done():
            task.cancel()
        raise CancelledError()

    if on_cancel is None:
        on_cancel = _default_cancel
    return await _wait_with_heartbeat(task, on_cancel=on_cancel)


def _make_cancel_handler(
    task: asyncio.Task, *, stop_callback: Callable[[], None] | None
):
    async def _handle_cancel() -> None:
        if stop_callback is not None:
            stop_callback()
            try:
                await task
            finally:
                raise CancelledError()
        if not task.done():
            task.cancel()
        raise CancelledError()

    return _handle_cancel


@activity.defn(name="llm_respond")
async def llm_respond(payload: LLMRequest) -> str:
    task = asyncio.create_task(
        asyncio.to_thread(
            reply,
            payload.text,
            payload.history,
            payload.search_results,
        )
    )
    return await _run_task(task)


@activity.defn(name="synthesize_audio_file")
async def synthesize_audio_file(text: str) -> str:
    tts = get_tts_engine()
    synth_task = asyncio.create_task(asyncio.to_thread(tts.synthesize, text))
    audio, sample_rate = await _run_task(synth_task)

    if activity.is_cancelled():
        raise CancelledError()

    with tempfile.NamedTemporaryFile(
        prefix="home-ai-tts-", suffix=".wav", delete=False
    ) as tmp_file:
        path = tmp_file.name
    try:
        write_wav(path, audio, sample_rate)
    except Exception:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        raise
    return path


@activity.defn(name="play_audio_file")
async def play_audio_file(path: str) -> None:
    stop_event = threading.Event()
    player = get_audio_player()

    def _play_wav_file(path: str, cancel_check: Callable[[], bool]) -> None:
        audio, sample_rate = load_wav(path)
        player.play(audio, sample_rate, DEFAULT_PLAYBACK_SPEED, cancel_check, None)

    playback_task = asyncio.create_task(
        asyncio.to_thread(_play_wav_file, path, stop_event.is_set)
    )
    try:
        await _run_task(
            playback_task,
            on_cancel=_make_cancel_handler(playback_task, stop_callback=stop_event.set),
        )
    finally:
        if not playback_task.done():
            stop_event.set()


@activity.defn(name="cleanup_audio_file")
async def cleanup_audio_file(path: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)


@activity.defn(name="stop_audio")
async def stop_audio_activity() -> None:
    get_audio_player().stop()


@activity.defn(name="local_search")
async def local_search(query: str) -> list[dict[str, str | int]]:
    results = await asyncio.to_thread(search_local_docs, query)
    return [
        {
            "title": result.title,
            "path": result.path,
            "snippet": result.snippet,
            "score": result.score,
        }
        for result in results
    ]


@activity.defn(name="append_session_summary")
async def append_session_summary_activity(payload: dict[str, str]) -> None:
    try:
        await asyncio.to_thread(
            append_session_summary_from_transcript,
            payload.get("transcript", ""),
            payload["start_time_iso"],
        )
        await asyncio.to_thread(build_index)
        print("append_session_summary_activity: embeddings rebuilt")
    except Exception as exc:
        print(f"append_session_summary_activity: failed: {exc}")
