import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow

# Activity names are strings so this module stays import-safe inside the sandbox.
ACTIVITY_LLM_RESPOND = "llm_respond"
ACTIVITY_TTS = "text_to_speech"
ACTIVITY_PLAY_AUDIO = "play_audio"


@dataclass
class Status:
    input_version: int
    last_done_version: int
    latest_text: Optional[str]
    last_reply: Optional[str]
    running: bool


@workflow.defn
class ChatAgentWorkflow:
    def __init__(self) -> None:
        self.latest_text: Optional[str] = None
        self.input_version: int = 0  # 入力が更新されるたびに増える
        self.last_done_version: int = 0  # 最後に完了した入力のversion
        self.last_reply: Optional[str] = None
        self.running: bool = False

    @workflow.signal
    async def new_input(self, text: str) -> None:
        # 外部から「新しい発話（テキスト）」が来たらここに入る
        self.latest_text = text
        self.input_version += 1

    @workflow.query
    def status(self) -> Status:
        return Status(
            input_version=self.input_version,
            last_done_version=self.last_done_version,
            latest_text=self.latest_text,
            last_reply=self.last_reply,
            running=self.running,
        )

    @workflow.run
    async def run(self) -> None:
        # ずっと待ち受ける（セッション常駐）
        while True:
            # 最新入力が未処理になるまで待つ
            await workflow.wait_condition(
                lambda: self.latest_text is not None
                and self.input_version > self.last_done_version
            )
            my_version = self.input_version
            text = self.latest_text
            self.running = True

            reply = await self._do_pipeline(text, my_version)
            self.last_reply = reply
            self.last_done_version = my_version
            # 新しい入力が来ていなければ latest_text をクリア
            if self.input_version == my_version:
                self.latest_text = None
            self.running = False

    async def _do_pipeline(self, text: str, version: int) -> str:
        reply = await workflow.execute_activity(
            ACTIVITY_LLM_RESPOND,
            text,
            start_to_close_timeout=timedelta(seconds=30),
        )
        # 処理中に新しい入力が来た場合は残りの処理をスキップ
        if self.input_version != version:
            return reply
        audio = await workflow.execute_activity(
            ACTIVITY_TTS,
            reply,
            start_to_close_timeout=timedelta(seconds=30),
        )
        if self.input_version != version:
            return reply
        await workflow.execute_activity(
            ACTIVITY_PLAY_AUDIO,
            audio,
            start_to_close_timeout=timedelta(seconds=60),
        )
        return reply
