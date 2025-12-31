import shutil
import subprocess

import queue
import numpy as np
import sounddevice as sd
from ollama import chat
from TTS.api import TTS
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
# Increase to play synthesized speech faster (e.g., 1.0 is normal speed).
PLAYBACK_SPEED = 1.25


def record_until_enter():
    q = queue.Queue()

    def callback(indata, frames, time, status):
        if status:
            print(status)
        q.put(indata.copy())

    print("Recording... press Enter to stop.")
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=callback):
        input()
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
        play_audio(wav, tts.synthesizer.output_sample_rate, speed=PLAYBACK_SPEED)


if __name__ == "__main__":
    main()
