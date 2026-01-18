from datetime import timedelta
from typing import Optional

from temporalio import common, workflow


@workflow.defn
class ChatAgentWorkflow:
    def __init__(self) -> None:
        self.latest_text: Optional[str] = None
        self.processing_idx: int = 0
        self.last_processed_idx: int = 0

    def _arrived_new_input(self) -> bool:
        return self.processing_idx > self.last_processed_idx

    def _update_text(self, text: str) -> None:
        self.latest_text = text
        self.processing_idx += 1

    def _done_workflow(self, processed_idx: int) -> None:
        self.last_processed_idx = processed_idx

    def _abandon_activity(self, handle: workflow.ActivityHandle) -> None:
        def _swallow(fut) -> None:
            try:
                fut.exception()
            except Exception:
                pass

        handle.add_done_callback(_swallow)

    async def _wait_for_completion_or_new_input(
        self, handle: workflow.ActivityHandle, start_idx: int
    ) -> bool:
        await workflow.wait_condition(
            lambda: handle.done() or self.processing_idx > start_idx
        )
        return self.processing_idx > start_idx

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
        self._update_text(text)

    async def _execute_workflow(self, reply_with_voice: bool) -> str:
        while True:
            start_idx = self.processing_idx
            text = self.latest_text

            reply_handle = workflow.start_activity(
                "llm_respond",
                text,
                start_to_close_timeout=timedelta(seconds=30),
                cancellation_type=workflow.ActivityCancellationType.TRY_CANCEL,
                retry_policy=common.RetryPolicy(maximum_attempts=1),
            )

            if await self._wait_for_completion_or_new_input(reply_handle, start_idx):
                reply_handle.cancel()
                self._abandon_activity(reply_handle)
                continue

            reply = await reply_handle
            if self.processing_idx > start_idx:
                continue
            if reply_with_voice:
                speak_handle = workflow.start_activity(
                    "speak_text",
                    reply,
                    start_to_close_timeout=timedelta(seconds=60),
                    cancellation_type=workflow.ActivityCancellationType.TRY_CANCEL,
                    retry_policy=common.RetryPolicy(maximum_attempts=1),
                )
                if await self._wait_for_completion_or_new_input(
                    speak_handle, start_idx
                ):
                    await self._interrupt_speech(speak_handle)
                    self._abandon_activity(speak_handle)
                    continue
                await speak_handle
                if self.processing_idx > start_idx:
                    continue

            self._done_workflow(start_idx)
            return reply

    @workflow.run
    async def run(self, reply_with_voice: bool) -> None:
        while True:
            await workflow.wait_condition(self._arrived_new_input)
            print("Input: ", self.latest_text)
            result = await self._execute_workflow(reply_with_voice)
            print("Home AI: ", result)
