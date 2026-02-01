from datetime import timedelta
from typing import Awaitable, Callable, Optional

from temporalio import common, workflow


@workflow.defn
class ChatAgentWorkflow:
    def __init__(self) -> None:
        self.latest_text: Optional[str] = None
        self.generation: int = 0
        self.last_processed_generation: int = 0

    def _arrived_new_input(self) -> bool:
        return self.generation > self.last_processed_generation

    async def _interrupt_speech(self, handle: workflow.ActivityHandle) -> None:
        handle.cancel()
        try:
            await workflow.execute_local_activity(
                "stop_audio",
                start_to_close_timeout=timedelta(seconds=5),
            )
        except Exception:
            pass

    @workflow.signal
    async def new_text_input(self, text: str) -> None:
        self.latest_text = text
        self.generation += 1

    async def _run_activity_step(
        self,
        start_handle: Callable[[], workflow.ActivityHandle],
        start_generation: int,
        *,
        on_cancel: Optional[
            Callable[[workflow.ActivityHandle], Awaitable[None]]
        ] = None,
    ):
        handle = start_handle()
        await workflow.wait_condition(
            lambda: handle.done() or self.generation > start_generation
        )
        if self.generation > start_generation:
            handle.cancel()
            if on_cancel is not None:
                await on_cancel(handle)
            return True, None
        result = await handle
        return self.generation > start_generation, result

    async def _execute_workflow(self) -> str:
        while True:
            start_generation = self.generation
            text = self.latest_text

            restarted, reply = await self._run_activity_step(
                lambda: workflow.start_activity(
                    "llm_respond",
                    text,
                    start_to_close_timeout=timedelta(seconds=30),
                    cancellation_type=workflow.ActivityCancellationType.TRY_CANCEL,
                    retry_policy=common.RetryPolicy(maximum_attempts=1),
                ),
                start_generation,
            )
            if restarted:
                continue
            restarted, _ = await self._run_activity_step(
                lambda: workflow.start_activity(
                    "speak_text",
                    reply,
                    start_to_close_timeout=timedelta(seconds=60),
                    cancellation_type=workflow.ActivityCancellationType.TRY_CANCEL,
                    retry_policy=common.RetryPolicy(maximum_attempts=1),
                ),
                start_generation,
                on_cancel=self._interrupt_speech,
            )
            if restarted:
                continue

            self.last_processed_generation = start_generation
            return reply

    @workflow.run
    async def run(self) -> None:
        while True:
            await workflow.wait_condition(self._arrived_new_input)
            print("Input: ", self.latest_text)
            result = await self._execute_workflow()
            print("Home AI: ", result)
