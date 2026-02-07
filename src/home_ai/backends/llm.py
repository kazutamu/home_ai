from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


DEFAULT_OLLAMA_MODEL = "llava:7b"


class LLMClient(Protocol):
    def chat(self, messages: list[dict[str, str]], *, model: str | None = None) -> str:
        ...


@dataclass
class OllamaLLMClient:
    model: str = DEFAULT_OLLAMA_MODEL

    def chat(self, messages: list[dict[str, str]], *, model: str | None = None) -> str:
        from ollama import chat as ollama_chat

        response = ollama_chat(
            model=model or self.model,
            messages=messages,
            stream=False,
        )
        return response["message"]["content"].strip()


def get_default_llm_model() -> str:
    return os.environ.get("HOME_AI_LLM_MODEL", DEFAULT_OLLAMA_MODEL)


def create_llm_client() -> LLMClient:
    backend = os.environ.get("HOME_AI_LLM_BACKEND", "ollama").lower()
    if backend == "ollama":
        return OllamaLLMClient(model=get_default_llm_model())
    raise ValueError(f"Unsupported LLM backend: {backend}")
