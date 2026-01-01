import argparse
import asyncio
import time
from datetime import timedelta
from typing import Sequence

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

DEFAULT_SERVER_URL = "temporal://localhost:7233"
DEFAULT_TASK_QUEUE = "home_ai_task_queue"


@activity.defn
async def say(name: str) -> str:
    return f"Hello, {name}!"


@workflow.defn
class HomeAIWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            say,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )


async def run_worker(server_url: str, task_queue: str) -> None:
    client = await Client.connect(server_url)
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[HomeAIWorkflow],
        activities=[say],
    )
    print(
        f"Starting Temporal worker against {server_url} "
        f"listening on task queue '{task_queue}'..."
    )
    await worker.run()


async def run_sample_workflow(server_url: str, task_queue: str, name: str) -> str:
    client = await Client.connect(server_url)
    return await client.execute_workflow(
        HomeAIWorkflow.run,
        name,
        id=f"home-ai-{int(time.time())}",
        task_queue=task_queue,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Temporal demo worker or kick off the sample workflow."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    worker_parser = subparsers.add_parser("worker", help="Start the Temporal worker")
    worker_parser.add_argument(
        "--server",
        default=DEFAULT_SERVER_URL,
        help=f"Temporal server URL (default: {DEFAULT_SERVER_URL})",
    )
    worker_parser.add_argument(
        "--task-queue",
        default=DEFAULT_TASK_QUEUE,
        help=f"Task queue name (default: {DEFAULT_TASK_QUEUE})",
    )

    run_parser = subparsers.add_parser(
        "run", help="Execute the sample workflow once"
    )
    run_parser.add_argument(
        "name", nargs="?", default="Temporal User", help="Name to greet"
    )
    run_parser.add_argument(
        "--server",
        default=DEFAULT_SERVER_URL,
        help=f"Temporal server URL (default: {DEFAULT_SERVER_URL})",
    )
    run_parser.add_argument(
        "--task-queue",
        default=DEFAULT_TASK_QUEUE,
        help=f"Task queue name (default: {DEFAULT_TASK_QUEUE})",
    )
    return parser.parse_args(argv)


async def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.command == "worker":
        await run_worker(args.server, args.task_queue)
        return

    result = await run_sample_workflow(args.server, args.task_queue, args.name)
    print(f"Workflow result: {result}")


def cli(argv: Sequence[str] | None = None) -> None:
    asyncio.run(main(argv))


if __name__ == "__main__":
    cli()
