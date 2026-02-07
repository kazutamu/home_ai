# home_ai

Minimal uv project for a voice agent that:

- records mic audio when someone is talking,
- transcribes it with faster-whisper,
- gets a concise response from Ollama, and
- speaks the reply via Coqui TTS (played directly with ffplay).

## Prerequisites

- Python 3.11 (3.12 is not supported by Coqui TTS yet)
- `ffmpeg` (ffplay) on PATH
- Ollama running locally with `llava:7b` pulled
- `uv` installed (https://docs.astral.sh/uv/)

## Setup

```bash
uv venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
uv sync
```

## Run

- Ensure a Temporal server is running and reachable at `temporal://localhost:7233`
  (for local dev you can use `temporal server start-dev` or the Temporal Docker image).
- Start the worker on the default task queue: `uv run python -m home_ai.worker`
- Kick off the sample greeting workflow once: `uv run python -m home_ai.voice_input`

## To do

- Establish the RAG system such that the chat workflow can continue on conversation
- Let the AI system control Home appliance
