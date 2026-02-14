# home_ai

Minimal uv project for a voice agent that:

- records mic audio when someone is talking (WebRTC VAD),
- transcribes it with faster-whisper,
- answers with Ollama (optionally grounded on local docs),
- synthesizes speech with Coqui TTS, and
- streams audio over HTTP and can play locally via ffplay.

There are three entry points: `voice_input` (mic), `text_input` (CLI), and
`audio_stream_client` (play HTTP audio stream locally).

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
2. Start the backend (FastAPI + Temporal worker):
   `uv run python -m home_ai.web.server`
3. Start input:
   - Voice input: `uv run python -m home_ai.voice_input`
   - Text input: `uv run python -m home_ai.text_input`
4. (Optional) Play the HTTP audio stream locally:
   `uv run python -m home_ai.audio_stream_client`
5. (Optional) React dev client (Vite):
   - `cd web_client`
   - `npm install`
   - `npm run dev`
   - Open the URL shown by Vite (default `http://localhost:5173/`)
   - This proxies `/input`, `/voice`, and `/audio/stream` to
     `HOME_AI_WEB_PORT` (default `8080`).

### One-command dev startup

For local development, you can launch Temporal (if installed), backend, and the
Vite client together:

```bash
./scripts/start-dev.sh
```

Notes:

- If `temporal` CLI is not installed, the script assumes Temporal is already
  running on `localhost:7233`.
- If Temporal (`7233`) or backend (`HOME_AI_WEB_PORT`) is already running, the
  script reuses it instead of starting a duplicate process.
- If `HOME_AI_WEB_PORT` is occupied by a non-Home AI service, the script fails
  fast with guidance instead of proceeding with a broken setup.
- Frontend port can be overridden with `VITE_PORT` (default `5173`).
- Backend port follows `HOME_AI_WEB_PORT` (default `8080`).

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
- `HOME_AI_TTS_COQUI_SPEAKER_WAV`: Speaker reference WAV for XTTS streaming.
- `HOME_AI_TTS_COQUI_LANGUAGE`: Language code for XTTS streaming (default: `en`).
- `HOME_AI_AUDIO_STREAM_URL`: HTTP stream URL for the client
  (default: `http://localhost:8080/audio/stream`).
- `HOME_AI_WEB_HOST`: Web server host (default: `0.0.0.0`).
- `HOME_AI_WEB_PORT`: Web server port (default: `8080`).
- `VITE_API_TARGET`: Override Vite dev proxy target (default: `http://localhost:8080`).
- `OPENAI_API_KEY`: Required when `HOME_AI_LLM_BACKEND=openai`.
- `GEMINI_API_KEY` or `GOOGLE_API_KEY`: Required when `HOME_AI_LLM_BACKEND=gemini`.
- `HOME_AI_TTS_GOOGLE_LANGUAGE`: Google TTS language code (default: `en-US`).
- `HOME_AI_TTS_GOOGLE_VOICE`: Optional Google TTS voice name.
- `HOME_AI_TTS_GOOGLE_SAMPLE_RATE`: Output sample rate (default: `24000`).
- `GOOGLE_APPLICATION_CREDENTIALS`: Required for Google TTS if not using
  application default credentials.

## Notes on RAG

Local search indexes files under `docs/` (`.md`, `.txt`, `.rst`) using
`sentence-transformers` (`all-MiniLM-L6-v2`). The index is rebuilt at session
shutdown and used to provide context to the Ollama chat model.

## Notes on TTS Streaming

Coqui XTTS can stream audio chunks directly when using an XTTS model and a
speaker reference WAV. Non-streaming models (like VITS) and Google TTS will
use a temporary WAV file and stream it in chunks over HTTP.
