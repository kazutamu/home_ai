import asyncio
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from .agent_workflow import ChatAgentWorkflow

from .worker import WF_ID, TASK_QUEUE, LOCAL_HOST


async def main():
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

    while True:
        text = input("Enter text (or 'q' to quit): ").strip()
        if text.lower() == "q":
            print("Exiting.")
            break
        await handle.signal(ChatAgentWorkflow.new_text_input, text)


if __name__ == "__main__":
    asyncio.run(main())
