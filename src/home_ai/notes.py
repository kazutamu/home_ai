from __future__ import annotations

from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOTES_PATH = PROJECT_ROOT / "docs/conversation_notes.md"
SUMMARY_PROMPT = (
    "You are summarizing a Home AI session for internal documentation. "
    "Write concise Markdown with these sections: Summary, Decisions, "
    "Open Questions, Next Steps. Use short bullet lists. If a section "
    "has no content, write 'None.'"
)


def _ensure_header(path: Path, *, title: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n", encoding="utf-8")


def _parse_iso(iso_value: str) -> datetime:
    return datetime.fromisoformat(iso_value).astimezone()


def _generate_summary(transcript: str) -> str:
    from ollama import chat

    response = chat(
        model="llava:7b",
        messages=[
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": transcript},
        ],
        stream=False,
    )
    return response["message"]["content"].strip()


def append_session_summary_from_transcript(
    transcript: str, start_time_iso: str, end_time_iso: str | None = None
) -> None:
    if not transcript.strip():
        return
    summary = _generate_summary(transcript)
    _ensure_header(NOTES_PATH, title="Conversation Notes")
    start_time = _parse_iso(start_time_iso)
    end_time = (
        _parse_iso(end_time_iso) if end_time_iso else datetime.now().astimezone()
    )
    title = (
        "## Session Summary ("
        f"{start_time.isoformat(timespec='seconds')} to "
        f"{end_time.isoformat(timespec='seconds')})"
    )
    with NOTES_PATH.open("a", encoding="utf-8") as handle:
        handle.write("\n" + title + "\n\n" + summary + "\n")

