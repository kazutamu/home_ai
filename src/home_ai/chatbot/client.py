from ollama import chat

from ..config import CHAT_MODEL, SYSTEM_PROMPT


def reply(user_text: str) -> str:
    response = chat(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        stream=False,
    )
    return response["message"]["content"]
