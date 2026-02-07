import asyncio
import os
from temporalio.client import Client
from temporalio.worker import Worker

from .agent_activities import (
    append_session_summary_activity,
    cleanup_audio_file,
    llm_respond,
    local_search,
    play_audio_file,
    stop_audio_activity,
    synthesize_audio_file,
)
from .agent_workflow import ChatAgentWorkflow

TASK_QUEUE = "agent-q"
WF_ID = "chat-session-1"
LOCAL_HOST = "localhost:7233"


async def main():
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    client = await Client.connect(LOCAL_HOST)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ChatAgentWorkflow],
        activities=[
            append_session_summary_activity,
            llm_respond,
            local_search,
            synthesize_audio_file,
            play_audio_file,
            cleanup_audio_file,
            stop_audio_activity,
        ],
    )
    print("Worker started. Ctrl+C to stop.")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
