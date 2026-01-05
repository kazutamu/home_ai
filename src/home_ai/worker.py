import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

from .agent_activities import llm_respond, speak_text
from .agent_workflow import ChatAgentWorkflow

TASK_QUEUE = "agent-q"


async def main():
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ChatAgentWorkflow],
        activities=[llm_respond, speak_text],
    )
    print("Worker started. Ctrl+C to stop.")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
