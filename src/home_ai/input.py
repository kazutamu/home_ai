from .agent_workflow import ChatAgentWorkflow
from temporalio.client import Client
import asyncio

WF_ID = "chat-session-1"
TASK_QUEUE = "agent-q"


async def main():
    client = await Client.connect("localhost:7233")

    try:
        await client.start_workflow(
            ChatAgentWorkflow.run,
            id=WF_ID,
            task_queue=TASK_QUEUE,
        )
        print("Workflow started:", WF_ID)
    except Exception:
        print("Workflow already running:", WF_ID)

    handle = client.get_workflow_handle(WF_ID)

    while True:
        text = input("Enter text (or 'q' to quit): ").strip()
        if text.lower() == "q":
            print("Exiting.")
            break
        await handle.signal(ChatAgentWorkflow.new_text_input, text)
        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
