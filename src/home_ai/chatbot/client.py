from ollama import chat

CHAT_MODEL = "llava:7b"
SYSTEM_PROMPT = "Be concise and reply in no more than two short sentences."


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
