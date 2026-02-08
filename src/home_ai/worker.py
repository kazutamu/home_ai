import asyncio
import os
from temporalio.client import Client
from temporalio.worker import Worker

from .agent_activities import (
    append_session_summary_activity,
    cleanup_audio_file,
    llm_respond,
    local_search,
    synthesize_and_stream_audio,
    synthesize_audio_file,
    stream_audio_chunks,
)
from .agent_workflow import ChatAgentWorkflow
from .audio_stream import BROADCASTER, start_audio_stream_server
from .config import load_environment

TASK_QUEUE = "agent-q"
WF_ID = "chat-session-1"
LOCAL_HOST = "localhost:7233"


async def main():
    load_environment()
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    client = await Client.connect(LOCAL_HOST)
    BROADCASTER.attach_loop(asyncio.get_running_loop())
    host = os.environ.get("HOME_AI_AUDIO_STREAM_HOST", "0.0.0.0")
    port = int(os.environ.get("HOME_AI_AUDIO_STREAM_PORT", "8081"))
    runner = await start_audio_stream_server(host, port)
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
    print("Worker started. Ctrl+C to stop.")
    try:
        await worker.run()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
