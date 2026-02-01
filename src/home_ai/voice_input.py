import asyncio
import queue
from collections import deque

import numpy as np
import sounddevice as sd
import webrtcvad
from temporalio.client import Client

from .agent_workflow import ChatAgentWorkflow
from .models import Transcriber
from .worker import TASK_QUEUE, WF_ID, LOCAL_HOST

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)
VAD_MODE = 2
START_TRIGGER_FRAMES = 8
END_TRIGGER_FRAMES = 12

vad = webrtcvad.Vad(VAD_MODE)


def frame_is_speech(frame_f32: np.ndarray) -> bool:
    pcm16 = (np.clip(frame_f32, -1.0, 1.0) * 32767).astype(np.int16)
    return vad.is_speech(pcm16.tobytes(), SAMPLE_RATE)


async def main():
    transcriber = Transcriber()
    client = await Client.connect(LOCAL_HOST)

    try:
        await client.start_workflow(
            ChatAgentWorkflow.run,
            id=WF_ID,
            task_queue=TASK_QUEUE,
            args=[True],
        )
        print("Workflow started:", WF_ID)
    except Exception:
        print("Workflow already running:", WF_ID)
    except Exception as exc:
        print(f"Failed to start workflow: {exc}")
        return

    handle = client.get_workflow_handle(WF_ID)

    frame_buffer = deque(maxlen=START_TRIGGER_FRAMES)
    audio_queue: queue.Queue[np.ndarray] = queue.Queue()
    talking = False
    speech_streak = 0
    silence_streak = 0
    current_clip = []

    print("Listening... (Ctrl+C to stop)")

    def callback(indata, frames, time_info, status):
        nonlocal talking, speech_streak, silence_streak, current_clip

        if status:
            pass

        mono = indata[:, 0]

        is_speech = frame_is_speech(mono)

        if is_speech:
            speech_streak += 1
            silence_streak = 0
        else:
            silence_streak += 1
            speech_streak = 0

        if not talking and speech_streak >= START_TRIGGER_FRAMES:
            talking = True
            current_clip = list(frame_buffer)
            print("\n[START TALKING]")

        if talking:
            current_clip.append(mono.copy())
            print(".", end="", flush=True)

            if silence_streak >= END_TRIGGER_FRAMES:
                talking = False
                if current_clip:
                    audio_queue.put(np.concatenate(current_clip))
                    current_clip = []
                frame_buffer.clear()
                print("\n[END TALKING]")
        frame_buffer.append(mono.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=FRAME_SAMPLES,
        callback=callback,
    ):
        while True:
            try:
                audio = audio_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue

            if audio.size == 0:
                continue

            text = transcriber.transcribe(audio)
            if text:
                print(f"\n[TRANSCRIBED] {text}")
                await handle.signal(ChatAgentWorkflow.new_text_input, text)
            else:
                print("\n[WARN] No speech recognized.")


if __name__ == "__main__":
    asyncio.run(main())
