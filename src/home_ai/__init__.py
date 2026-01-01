import queue
import shutil
import subprocess

import numpy as np
import sounddevice as sd
from TTS.api import TTS
from faster_whisper import WhisperModel
from ollama import chat
from sounddevice import PortAudioError

SAMPLE_RATE = 16000
# Increase to play synthesized speech faster (e.g., 1.0 is normal speed).
PLAYBACK_SPEED = 1.25


def _pick_input_device() -> int:
    """Return an input-capable device index or raise with a clear message."""
    try:
        devices = sd.query_devices()
    except Exception as exc:  # pragma: no cover - passthrough diagnostics
        msg = f"Could not query audio devices: {exc}"
        raise RuntimeError(msg) from exc

    input_devices = [i for i, dev in enumerate(
        devices) if dev.get("max_input_channels", 0) > 0]
    if not input_devices:
        msg = (
            "No input audio devices found. If you are in a dev container, pass the host mic "
            "through (e.g., add --device /dev/snd) or run on the host."
        )
        raise RuntimeError(msg)

    default_device = sd.default.device
    if isinstance(default_device, (list, tuple)):
        default_in = default_device[0]
    else:
        # sounddevice may return an _InputOutputPair with an .input attribute
        default_in = getattr(default_device, "input", default_device)

    if isinstance(default_in, (int, float)) and default_in >= 0:
        return int(default_in)

    return input_devices[0]


def record_until_enter():
    q = queue.Queue()

    def callback(indata, frames, time, status):
        if status:
            print(status)
        q.put(indata.copy())

    device = _pick_input_device()
    print(f"Recording (device {device})... press Enter to stop.")
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=callback, device=device):
            input()
    except PortAudioError as exc:
        msg = (
            f"Could not open input device {device}: {exc}. "
            "Check that your microphone is available to the container or select a valid device."
        )
        raise RuntimeError(msg) from exc
    chunks = []
    while not q.empty():
        chunks.append(q.get())
    return np.concatenate(chunks, axis=0).flatten()


def play_audio(wav, sample_rate: int, speed: float = 1.0) -> None:
    """Play a waveform in-memory using ffplay so we don't write to disk."""
    if shutil.which("ffplay") is None:
        msg = "ffplay is required to play audio without saving a file."
        raise RuntimeError(msg)

    audio = np.clip(np.asarray(wav), -1.0, 1.0)
    pcm_bytes = (audio * 32767).astype(np.int16).tobytes()

    cmd = [
        "ffplay",
        "-autoexit",
        "-nodisp",
        "-f",
        "s16le",
        "-ar",
        str(sample_rate),
        "-",
        "-af",
        f"atempo={speed}",
    ]
    with subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ) as proc:
        assert proc.stdin is not None
        proc.stdin.write(pcm_bytes)
        proc.stdin.close()
        proc.wait()


def main():
    print("Press Enter to record, or type 'q' then Enter to quit.")
    whisper = WhisperModel("base", device="cpu", compute_type="int8")
    tts = TTS("tts_models/en/ljspeech/tacotron2-DDC")

    while True:
        cmd = input("Ready? (Enter=record, q=quit): ").strip().lower()
        if cmd.startswith("q"):
            print("Exiting.")
            break

        audio = record_until_enter()
        if audio.size == 0:
            print("No audio captured, try again.")
            continue

        segments, _ = whisper.transcribe(
            audio, language="en", beam_size=5, vad_filter=True
        )
        input_text = " ".join(seg.text for seg in segments).strip()
        if not input_text:
            print("Could not understand audio, try again.")
            continue

        print(f"Heard: {input_text}")
        response = chat(
            model="llava:7b",
            messages=[
                {
                    "role": "system",
                    "content": "Be concise and reply in no more than two short sentences.",
                },
                {"role": "user", "content": input_text},
            ],
            stream=False,
        )
        output_text = response["message"]["content"]
        print(f"LLM Response: {output_text}")

        wav = tts.tts(text=output_text)
        play_audio(wav, tts.synthesizer.output_sample_rate,
                   speed=PLAYBACK_SPEED)


__all__ = ["main", "play_audio", "record_until_enter",
           "SAMPLE_RATE", "PLAYBACK_SPEED"]
