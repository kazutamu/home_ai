from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow


def append_history(
    history: list[dict[str, str]],
    user_text: str | None,
    reply: str | None,
) -> list[dict[str, str]]:
    if user_text:
        history.append({"role": "user", "content": user_text})
    if reply:
        history.append({"role": "assistant", "content": reply})
    return history


def history_for_llm(
    history: list[dict[str, str]],
    *,
    max_turns: int,
) -> list[dict[str, str]]:
    max_messages = max_turns * 2
    if len(history) <= max_messages:
        return list(history)
    return list(history[-max_messages:])


def build_history_transcript(history: list[dict[str, str]]) -> str:
    if not history:
        return ""
    parts: list[str] = []
    for entry in history:
        role = entry.get("role", "assistant").title()
        content = entry.get("content", "")
        if not content:
            continue
        parts.append(f"{role}: {content}")
    return "\n\n".join(parts)


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
