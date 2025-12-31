import shutil
import subprocess

import numpy as np
from ollama import chat
from TTS.api import TTS


def play_audio(wav, sample_rate: int) -> None:
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
    ]
    with subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ) as proc:
        assert proc.stdin is not None
        proc.stdin.write(pcm_bytes)
        proc.stdin.close()
        proc.wait()


def main():
    tts = TTS("tts_models/en/ljspeech/tacotron2-DDC")
    while True:
        input_string = input("Enter a question: ")

        if input_string.lower() in {"exit", "quit"}:
            break

        response = chat(
            model="llava:7b",
            messages=[{"role": "user", "content": input_string}],
            stream=False,
        )

        text = response["message"]["content"]
        print(f"LLM Response: {text}")
        wav = tts.tts(text=text)
        play_audio(wav, tts.synthesizer.output_sample_rate)


if __name__ == "__main__":
    main()
