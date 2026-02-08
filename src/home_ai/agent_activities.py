import asyncio
import contextlib
import os
import tempfile
from temporalio import activity
from temporalio.exceptions import CancelledError

from .audio import load_wav, write_wav
from .audio_stream import BROADCASTER, DEFAULT_CHUNK_SIZE, float_to_pcm16
from .backends import get_tts_engine
from .chatbot import reply
from .notes.conversation_notes import append_session_summary_from_transcript
from .search.embedding_search import build_index, search_local_docs
from .workflow_utils import LLMRequest

async def _run_task(task: asyncio.Task):
    while True:
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=0.1)
        except asyncio.TimeoutError:
            if activity.is_cancelled():
                if not task.done():
                    task.cancel()
                raise CancelledError()
            activity.heartbeat()


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


@activity.defn(name="synthesize_and_stream_audio")
async def synthesize_and_stream_audio(text: str) -> None:
    tts = get_tts_engine()
    speaker_wav = os.environ.get("HOME_AI_TTS_COQUI_SPEAKER_WAV")
    language = os.environ.get("HOME_AI_TTS_COQUI_LANGUAGE", "en")

    if hasattr(tts, "supports_streaming") and tts.supports_streaming() and speaker_wav:
        BROADCASTER.set_sample_rate(tts.output_sample_rate())
        for chunk in tts.stream(text, speaker_wav=speaker_wav, language=language):
            if activity.is_cancelled():
                raise CancelledError()
            BROADCASTER.publish(float_to_pcm16(chunk))
            activity.heartbeat()
            await asyncio.sleep(0)
        return

    path = await synthesize_audio_file(text)
    try:
        await stream_audio_chunks(path)
    finally:
        await cleanup_audio_file(path)


@activity.defn(name="stream_audio_chunks")
async def stream_audio_chunks(path: str) -> None:
    audio, sample_rate = await asyncio.to_thread(load_wav, path)
    BROADCASTER.set_sample_rate(sample_rate)
    pcm_bytes = float_to_pcm16(audio)

    bytes_per_sample = 2
    for idx in range(0, len(pcm_bytes), DEFAULT_CHUNK_SIZE):
        if activity.is_cancelled():
            raise CancelledError()
        chunk = pcm_bytes[idx : idx + DEFAULT_CHUNK_SIZE]
        BROADCASTER.publish(chunk)
        activity.heartbeat()
        # Pace sending to roughly real-time to avoid client-side buffering delay.
        await asyncio.sleep(len(chunk) / (bytes_per_sample * sample_rate))


@activity.defn(name="cleanup_audio_file")
async def cleanup_audio_file(path: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)


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
