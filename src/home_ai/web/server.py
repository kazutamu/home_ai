from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from temporalio.client import Client
from temporalio.worker import Worker
import uvicorn

from ..agent_activities import (
    append_session_summary_activity,
    cleanup_audio_file,
    llm_respond,
    local_search,
    synthesize_and_stream_audio,
    synthesize_audio_file,
    stream_audio_chunks,
)
from ..agent_workflow import ChatAgentWorkflow
from ..audio.stream import BROADCASTER, stream_generator, stream_headers
from ..audio.wav import load_wav_bytes
from ..config import load_environment
from ..input.runner import ensure_workflow_handle, normalize_shutdown_command
from ..models.transcription import Transcriber
from ..runtime import LOCAL_HOST, TASK_QUEUE

DEFAULT_WEB_HOST = "0.0.0.0"
DEFAULT_WEB_PORT = 8080


def _load_index_html() -> Optional[str]:
    index_path = Path(__file__).resolve().parent / "index.html"
    if not index_path.exists():
        return None
    return index_path.read_text(encoding="utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_environment()
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    client = await Client.connect(LOCAL_HOST)
    app.state.temporal_client = client
    app.state.transcriber = None
    BROADCASTER.attach_loop(asyncio.get_running_loop())

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ChatAgentWorkflow],
        activities=[
            append_session_summary_activity,
            llm_respond,
            local_search,
            synthesize_and_stream_audio,
            synthesize_audio_file,
            stream_audio_chunks,
            cleanup_audio_file,
        ],
    )
    worker_task = asyncio.create_task(worker.run())
    try:
        yield
    finally:
        worker_task.cancel()
        with suppress(Exception):
            await worker_task


app = FastAPI(lifespan=lifespan)
_INDEX_HTML = _load_index_html()


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    if _INDEX_HTML is None:
        return HTMLResponse("Home AI backend running.", status_code=200)
    return HTMLResponse(_INDEX_HTML, status_code=200)


@app.post("/input")
async def input_text(payload: dict) -> JSONResponse:
    raw = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        raise HTTPException(status_code=400, detail="text is required")

    text = raw.strip()
    client: Client = app.state.temporal_client
    try:
        # Cut any in-flight/queued audio immediately when a new user entry arrives.
        BROADCASTER.interrupt()
        handle = await ensure_workflow_handle(client, quiet=True)
        if normalize_shutdown_command(text):
            await handle.signal(ChatAgentWorkflow.request_shutdown)
        else:
            await handle.signal(ChatAgentWorkflow.new_text_input, text)
    except Exception:
        raise HTTPException(status_code=500, detail="failed to submit text")

    return JSONResponse({"ok": True})


@app.post("/voice/transcribe")
async def transcribe_voice(audio: UploadFile = File(...)) -> JSONResponse:
    content_type = (audio.content_type or "").lower()
    filename = (audio.filename or "").lower()
    if "wav" not in content_type and not filename.endswith(".wav"):
        raise HTTPException(status_code=400, detail="audio must be WAV")

    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="audio is empty")

    try:
        pcm, _ = await run_in_threadpool(load_wav_bytes, data)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid WAV audio")

    if pcm.size == 0:
        raise HTTPException(status_code=400, detail="audio is empty")

    transcriber: Optional[Transcriber] = app.state.transcriber
    if transcriber is None:
        transcriber = await run_in_threadpool(Transcriber)
        app.state.transcriber = transcriber
    text = await run_in_threadpool(transcriber.transcribe, pcm)
    return JSONResponse({"text": text})


@app.get("/audio/stream")
async def audio_stream() -> StreamingResponse:
    headers = stream_headers()
    return StreamingResponse(stream_generator(), headers=headers, media_type="application/octet-stream")


def main() -> None:
    host = os.environ.get("HOME_AI_WEB_HOST", DEFAULT_WEB_HOST)
    port = int(os.environ.get("HOME_AI_WEB_PORT", str(DEFAULT_WEB_PORT)))
    uvicorn.run(
        "home_ai.web.server:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
