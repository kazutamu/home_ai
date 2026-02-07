# home_ai

Minimal uv project for a voice agent that:

- records mic audio when someone is talking (WebRTC VAD),
- transcribes it with faster-whisper,
- answers with Ollama (optionally grounded on local docs),
- synthesizes speech with Coqui TTS, and
- plays audio via ffplay with cancel support.

There are two entry points: `voice_input` (mic) and `text_input` (CLI).

## Prerequisites

- Python 3.11 (3.12 is not supported by Coqui TTS yet)
- `ffmpeg` (ffplay) on PATH
- Ollama running locally with `llava:7b` pulled
- `uv` installed (https://docs.astral.sh/uv/)
- A running Temporal server at `localhost:7233`

## Setup

```bash
uv venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
uv sync
```

Create a `.env` file (see `.env.example`) and fill in any required secrets
such as `OPENAI_API_KEY`.

## Run

1. Start a Temporal server (for local dev you can use `temporal server start-dev`).
2. Start the worker on the default task queue:
   `uv run python -m home_ai.worker`
3. Start input:
   - Voice input: `uv run python -m home_ai.voice_input`
   - Text input: `uv run python -m home_ai.text_input`

Stopping:

- In voice mode, say "quit", "exit", or "stop" to end the session.
- In text mode, enter `q`.

On shutdown, the workflow writes a session summary to `docs/conversation_notes.md`
and rebuilds a local embedding index in `data/` for retrieval-augmented responses.

## Configuration

- `HOME_AI_LLM_BACKEND`: LLM backend (default: `ollama`).
- `HOME_AI_LLM_MODEL`: Ollama model name (default: `llava:7b`).
- `HOME_AI_TTS_BACKEND`: TTS backend (default: `coqui`).
- `HOME_AI_TTS_MODEL`: Override the Coqui TTS model (default:
  `tts_models/en/vctk/vits`).
- `HOME_AI_AUDIO_BACKEND`: Audio playback backend (default: `ffplay`).
- `OPENAI_API_KEY`: Required when `HOME_AI_LLM_BACKEND=openai`.
- `GEMINI_API_KEY` or `GOOGLE_API_KEY`: Required when `HOME_AI_LLM_BACKEND=gemini`.

## Notes on RAG

Local search indexes files under `docs/` (`.md`, `.txt`, `.rst`) using
`sentence-transformers` (`all-MiniLM-L6-v2`). The index is rebuilt at session
shutdown and used to provide context to the Ollama chat model.
