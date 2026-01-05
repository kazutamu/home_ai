from datetime import timedelta
from typing import Optional

from temporalio import workflow


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

    def _done_workflow(self) -> None:
        self.last_processed_idx = self.processing_idx

    @workflow.signal
    async def new_text_input(self, text: str) -> None:
        self._update_text(text)

    async def _execute_workflow(self, reply_with_voice: bool) -> str:
        reply = await workflow.execute_activity(
            "llm_respond",
            self.latest_text,
            start_to_close_timeout=timedelta(seconds=30),
        )
        if reply_with_voice:
            await workflow.execute_activity(
                "speak_text",
                reply,
                start_to_close_timeout=timedelta(seconds=60),
            )

        self._done_workflow()
        return reply

    @workflow.run
    async def run(self, reply_with_voice: bool) -> None:
        while True:
            await workflow.wait_condition(self._arrived_new_input)
            print("Input: ", self.latest_text)
            result = await self._execute_workflow(reply_with_voice)
            print("Home AI: ", result)
