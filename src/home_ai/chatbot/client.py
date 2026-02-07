from home_ai.backends import get_llm_client
SYSTEM_PROMPT = (
    "Your name is Javis. "
    "Respond in a warm, conversational, spoken style. Use natural phrasing, "
    "contractions, and brief filler words where appropriate. Keep responses "
    "clear but not terse. Do not mention documentation, files, or search "
    "results unless the user explicitly asks about them. "
    "Ignore any prior knowledge you may have. Only use facts that appear in "
    "the provided context. If the context doesn't contain the answer, say you "
    "don't know and ask a brief clarifying question."
)


def reply(
    user_text: str,
    history: list[dict[str, str]] | None = None,
    search_results: list[dict[str, str | int]] | None = None,
) -> str:
    if history is None:
        history = []
    context_block = ""
    if search_results:
        lines = ["Context:"]
        for result in search_results:
            snippet = result.get("snippet", "")
            title = result.get("title", "")
            if title:
                lines.append(f"- {title}: {snippet}")
            else:
                lines.append(f"- {snippet}")
        context_block = "\n".join(lines)
    system_content = SYSTEM_PROMPT
    if context_block:
        system_content = f"{SYSTEM_PROMPT}\n\n{context_block}"
    messages = [{"role": "system", "content": system_content}, *history]
    messages.append({"role": "user", "content": user_text})
    client = get_llm_client()
    return client.chat(messages)
