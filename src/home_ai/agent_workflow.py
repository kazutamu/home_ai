from temporalio import workflow
from dataclasses import dataclass
from typing import Optional


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

    @workflow.run
    async def run(self) -> None:
        while True:
            await workflow.wait_condition(
                lambda: self.latest_text is not None
                and self.input_version > self.last_done_version
            )
            print("New input received:", self.latest_text)
            self.last_done_version = self.input_version
