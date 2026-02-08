from __future__ import annotations

from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from ..agent_workflow import ChatAgentWorkflow
from ..config import load_environment
from ..worker import LOCAL_HOST, TASK_QUEUE, WF_ID
from .interface import InputEventType, InputSource


def _normalize_shutdown_command(text: str) -> bool:
    normalized = text.strip().lower().strip(" .,!?:;\"'")
    return normalized in {"quit", "exit", "stop"}


async def run_input_source(source: InputSource) -> None:
    load_environment()
    client = await Client.connect(LOCAL_HOST)

    try:
        await client.start_workflow(
            ChatAgentWorkflow.run,
            id=WF_ID,
            task_queue=TASK_QUEUE,
        )
        print("Workflow started:", WF_ID)
    except WorkflowAlreadyStartedError:
        print("Workflow already running:", WF_ID)
    except Exception as exc:
        print(f"Failed to start workflow: {exc}")
        return

    handle = client.get_workflow_handle(WF_ID)

    async for event in source.events():
        if event.type == InputEventType.SHUTDOWN:
            print("[INFO] Quit requested. Summarizing session.")
            await handle.signal(ChatAgentWorkflow.request_shutdown)
            break
        if event.type == InputEventType.TEXT:
            if not event.text:
                continue
            if _normalize_shutdown_command(event.text):
                print("[INFO] Quit requested. Summarizing session.")
                await handle.signal(ChatAgentWorkflow.request_shutdown)
                break
            await handle.signal(ChatAgentWorkflow.new_text_input, event.text)
