# home_ai

Minimal uv project for a voice agent that:
- records mic audio until you press Enter,
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
```bash
uv run python -m home_ai.main
```

While running, press Enter to start/stop recording; type `q` + Enter to quit.
