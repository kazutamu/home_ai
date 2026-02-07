from datetime import timedelta
from typing import Awaitable, Callable, Optional

from temporalio import common, workflow

from home_ai.workflow_utils import (
    cleanup_audio_file,
    interrupt_speech,
    LLMRequest,
    update_history,
)


@workflow.defn
class ChatAgentWorkflow:
    def __init__(self) -> None:
        self.latest_text: Optional[str] = None
        self.generation: int = 0
        self.last_processed_generation: int = 0
        self.history: list[dict[str, str]] = []
        self.max_history_turns: int = 10

    def _arrived_new_input(self) -> bool:
        return self.generation > self.last_processed_generation

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
        on_cancel_result: Optional[Callable[[object], Awaitable[None]]] = None,
    ):
        handle = start_handle()
        await workflow.wait_condition(
            lambda: handle.done() or self.generation > start_generation
        )
        if self.generation > start_generation:
            if handle.done():
                try:
                    result = await handle
                except Exception:
                    result = None
                if on_cancel_result is not None and result is not None:
                    await on_cancel_result(result)
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

            restarted, search_results = await self._run_activity_step(
                lambda: workflow.start_activity(
                    "local_search",
                    text or "",
                    start_to_close_timeout=timedelta(seconds=10),
                    cancellation_type=workflow.ActivityCancellationType.TRY_CANCEL,
                    retry_policy=common.RetryPolicy(maximum_attempts=1),
                ),
                start_generation,
            )
            if restarted:
                continue

            restarted, reply = await self._run_activity_step(
                lambda: workflow.start_activity(
                    "llm_respond",
                    LLMRequest(
                        text=text or "",
                        history=list(self.history),
                        search_results=search_results or [],
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    cancellation_type=workflow.ActivityCancellationType.TRY_CANCEL,
                    retry_policy=common.RetryPolicy(maximum_attempts=1),
                ),
                start_generation,
            )
            if restarted:
                continue

            restarted, audio_path = await self._run_activity_step(
                lambda: workflow.start_activity(
                    "synthesize_audio_file",
                    reply,
                    start_to_close_timeout=timedelta(seconds=60),
                    cancellation_type=workflow.ActivityCancellationType.TRY_CANCEL,
                    retry_policy=common.RetryPolicy(maximum_attempts=1),
                ),
                start_generation,
                on_cancel_result=cleanup_audio_file,
            )
            if restarted:
                continue

            try:
                restarted, _ = await self._run_activity_step(
                    lambda: workflow.start_activity(
                        "play_audio_file",
                        audio_path,
                        start_to_close_timeout=timedelta(seconds=60),
                        cancellation_type=workflow.ActivityCancellationType.TRY_CANCEL,
                        retry_policy=common.RetryPolicy(maximum_attempts=1),
                    ),
                    start_generation,
                    on_cancel=interrupt_speech,
                )
                if restarted:
                    continue

                self.history = update_history(
                    self.history,
                    text,
                    reply,
                    max_turns=self.max_history_turns,
                )
                self.last_processed_generation = start_generation
                return reply
            finally:
                await cleanup_audio_file(audio_path)

    @workflow.run
    async def run(self) -> None:
        while True:
            await workflow.wait_condition(self._arrived_new_input)
            print("Input: ", self.latest_text)
            result = await self._execute_workflow()
            print("Home AI: ", result)
