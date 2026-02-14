from datetime import timedelta
from typing import Awaitable, Callable, Optional

from temporalio import common, workflow

from home_ai.workflow_utils import (
    append_history,
    build_history_transcript,
    history_for_llm,
    LLMRequest,
)


@workflow.defn
class ChatAgentWorkflow:
    def __init__(self) -> None:
        self.latest_text: Optional[str] = None
        self.generation: int = 0
        self.last_processed_generation: int = 0
        self.history: list[dict[str, str]] = []
        self.max_history_turns: int = 10
        self.shutdown_requested: bool = False

    def _arrived_new_input(self) -> bool:
        return self.generation > self.last_processed_generation

    @workflow.signal
    async def new_text_input(self, text: str) -> None:
        self.latest_text = text
        self.generation += 1

    @workflow.signal
    async def request_shutdown(self) -> None:
        self.shutdown_requested = True

    async def _run_activity_step(
        self,
        start_handle: Callable[[], workflow.ActivityHandle],
        start_generation: int,
        *,
        on_cancel_result: Optional[Callable[[object], Awaitable[None]]] = None,
    ):
        handle = start_handle()
        await workflow.wait_condition(
            lambda: handle.done() or self.generation > start_generation
        )
        if self.generation > start_generation:
            result = None
            if handle.done():
                try:
                    result = await handle
                except Exception:
                    result = None
            if on_cancel_result is not None and result is not None:
                await on_cancel_result(result)
            handle.cancel()
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
                        history=history_for_llm(self.history, max_turns=self.max_history_turns),
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
            restarted, _ = await self._run_activity_step(
                lambda: workflow.start_activity(
                    "synthesize_and_stream_audio",
                    reply,
                    start_to_close_timeout=timedelta(seconds=120),
                    cancellation_type=workflow.ActivityCancellationType.TRY_CANCEL,
                    retry_policy=common.RetryPolicy(maximum_attempts=1),
                ),
                start_generation,
            )
            if restarted:
                continue

            append_history(self.history, text, reply)
            self.last_processed_generation = start_generation
            return reply

    @workflow.run
    async def run(self) -> None:
        while True:
            await workflow.wait_condition(
                lambda: self._arrived_new_input() or self.shutdown_requested
            )
            if self.shutdown_requested:
                try:
                    transcript = build_history_transcript(self.history)
                    await workflow.execute_activity(
                        "append_session_summary",
                        {
                            "start_time_iso": workflow.now().isoformat(
                                timespec="seconds"
                            ),
                            "transcript": transcript,
                        },
                        start_to_close_timeout=timedelta(seconds=30),
                        cancellation_type=workflow.ActivityCancellationType.TRY_CANCEL,
                        retry_policy=common.RetryPolicy(maximum_attempts=1),
                    )
                except Exception:
                    pass
                return
            print("Input: ", self.latest_text)
            result = await self._execute_workflow()
            print("Home AI: ", result)
