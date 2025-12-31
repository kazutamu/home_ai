import shutil
import subprocess

import queue
import numpy as np
import sounddevice as sd
from ollama import chat
from TTS.api import TTS
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000


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
    audio = record_until_enter()
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        audio, language="en", beam_size=5, vad_filter=True
    )
    input_text = " ".join(seg.text for seg in segments)
    print(f"Heard: {input_text}")
    response = chat(
        model="llava:7b",
        messages=[{"role": "user", "content": input_text}],
        stream=False,
    )
    output_text = response["message"]["content"]
    print(f"LLM Response: {output_text}")
    tts = TTS("tts_models/en/ljspeech/tacotron2-DDC")
    wav = tts.tts(text=output_text)

    play_audio(wav, tts.synthesizer.output_sample_rate)


if __name__ == "__main__":
    main()
