from ollama import chat

CHAT_MODEL = "llava:7b"
SYSTEM_PROMPT = (
    "Respond in a warm, conversational, spoken style. Use natural phrasing, "
    "contractions, and brief filler words where appropriate. Keep responses "
    "clear but not terse."
)


def reply(user_text: str, history: list[dict[str, str]] | None = None) -> str:
    if history is None:
        history = []
    response = chat(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": user_text},
        ],
        stream=False,
    )
    return response["message"]["content"]
