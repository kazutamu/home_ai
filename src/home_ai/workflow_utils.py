from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow


def update_history(
    history: list[dict[str, str]],
    user_text: str | None,
    reply: str | None,
    *,
    max_turns: int,
) -> list[dict[str, str]]:
    updated = list(history)
    if user_text:
        updated.append({"role": "user", "content": user_text})
    if reply:
        updated.append({"role": "assistant", "content": reply})
    max_messages = max_turns * 2
    if len(updated) > max_messages:
        updated = updated[-max_messages:]
    return updated


async def interrupt_speech(handle: workflow.ActivityHandle) -> None:
    handle.cancel()
    try:
        await workflow.execute_local_activity(
            "stop_audio",
            start_to_close_timeout=timedelta(seconds=5),
        )
    except Exception:
        pass


async def cleanup_audio_file(path: Optional[str]) -> None:
    if not path:
        return
    try:
        await workflow.execute_local_activity(
            "cleanup_audio_file",
            path,
            start_to_close_timeout=timedelta(seconds=5),
        )
    except Exception:
        pass
@dataclass
class LLMRequest:
    text: str
    history: list[dict[str, str]]
    search_results: list[dict[str, str | int]] | None = None
