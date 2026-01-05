from dataclasses import dataclass
from datetime import timedelta
from typing import Literal, Optional

from temporalio import workflow

ReplyStyle = Literal["text", "audio"]
REPLY_STYLE_TEXT: ReplyStyle = "text"
REPLY_STYLE_AUDIO: ReplyStyle = "audio"


@dataclass
class Status:
    latest_text: Optional[str]
    input_version: int = 0
    last_done_version: int = 0


@workflow.defn
class ChatAgentWorkflow:
    def __init__(self) -> None:
        self.latest_text: Optional[str] = None
        self.input_version: int = 0
        self.last_done_version: int = 0

    @workflow.signal
    async def new_text_input(self, text: str) -> None:
        self.latest_text = text
        self.input_version += 1

    async def _execute_workflow(self, style: ReplyStyle = REPLY_STYLE_AUDIO) -> str:
        if self.latest_text is None:
            return "No input text available"
        reply = await workflow.execute_activity(
            "llm_respond",
            self.latest_text,
            start_to_close_timeout=timedelta(seconds=30),
        )
        if style == REPLY_STYLE_AUDIO:
            await workflow.execute_activity(
                "speak_text",
                reply,
                start_to_close_timeout=timedelta(seconds=60),
            )

        return reply

    @workflow.run
    async def run(self, reply_style: ReplyStyle = REPLY_STYLE_AUDIO) -> None:
        while True:
            await workflow.wait_condition(
                lambda: self.latest_text is not None
                and self.input_version > self.last_done_version
            )
            result = await self._execute_workflow(reply_style)
            print("Workflow result:", result)
            self.last_done_version = self.input_version
