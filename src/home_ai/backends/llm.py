from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


DEFAULT_OLLAMA_MODEL = "llava:7b"
DEFAULT_OPENAI_MODEL = "gpt-5.2"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class LLMClient(Protocol):
    def chat(
        self, messages: list[dict[str, str]], *, model: str | None = None
    ) -> str: ...


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


@dataclass
class OpenAILLMClient:
    model: str = DEFAULT_OPENAI_MODEL

    def __post_init__(self) -> None:
        from openai import OpenAI

        self._client = OpenAI()

    def chat(self, messages: list[dict[str, str]], *, model: str | None = None) -> str:
        instructions = None
        input_items: list[dict[str, object]] = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system" and instructions is None:
                instructions = content
                continue
            if not content:
                continue
            input_items.append(
                {
                    "role": role,
                    "content": [{"type": "input_text", "text": content}],
                }
            )
        if not input_items:
            input_payload: object = ""
        else:
            input_payload = input_items
        response = self._client.responses.create(
            model=model or self.model,
            instructions=instructions,
            input=input_payload,
        )
        return response.output_text


@dataclass
class GeminiLLMClient:
    model: str = DEFAULT_GEMINI_MODEL

    def __post_init__(self) -> None:
        from google import genai

        self._client = genai.Client()

    def chat(self, messages: list[dict[str, str]], *, model: str | None = None) -> str:
        system_text: str | None = None
        parts: list[str] = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if not content:
                continue
            if role == "system" and system_text is None:
                system_text = content
                continue
            parts.append(f"{role.title()}: {content}")
        prompt = "\n\n".join(parts) if parts else ""
        if system_text:
            prompt = f"{system_text}\n\n{prompt}" if prompt else system_text
        response = self._client.models.generate_content(
            model=model or self.model,
            contents=prompt,
        )
        return (response.text or "").strip()


def get_default_llm_model() -> str:
    override = os.environ.get("HOME_AI_LLM_MODEL")
    if override:
        return override
    backend = os.environ.get("HOME_AI_LLM_BACKEND", "ollama").lower()
    if backend == "openai":
        return DEFAULT_OPENAI_MODEL
    if backend == "gemini":
        return DEFAULT_GEMINI_MODEL
    return DEFAULT_OLLAMA_MODEL


def create_llm_client() -> LLMClient:
    backend = os.environ.get("HOME_AI_LLM_BACKEND", "ollama").lower()
    if backend == "ollama":
        return OllamaLLMClient(model=get_default_llm_model())
    if backend == "openai":
        return OpenAILLMClient(model=get_default_llm_model())
    if backend == "gemini":
        return GeminiLLMClient(model=get_default_llm_model())
    raise ValueError(f"Unsupported LLM backend: {backend}")
