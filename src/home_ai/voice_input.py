import asyncio
import queue
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import sounddevice as sd
import webrtcvad
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from .agent_workflow import ChatAgentWorkflow
from .config import load_environment
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


@dataclass
class SpeechSegmenter:
    frame_buffer: deque = field(default_factory=lambda: deque(maxlen=START_TRIGGER_FRAMES))
    talking: bool = False
    speech_streak: int = 0
    silence_streak: int = 0
    current_clip: list[np.ndarray] = field(default_factory=list)

    def process_frame(self, mono: np.ndarray) -> Optional[np.ndarray]:
        is_speech = frame_is_speech(mono)

        if is_speech:
            self.speech_streak += 1
            self.silence_streak = 0
        else:
            self.silence_streak += 1
            self.speech_streak = 0

        if not self.talking and self.speech_streak >= START_TRIGGER_FRAMES:
            self.talking = True
            self.current_clip = list(self.frame_buffer)
            print("\n[START TALKING]")

        if self.talking:
            self.current_clip.append(mono.copy())
            print(".", end="", flush=True)

            if self.silence_streak >= END_TRIGGER_FRAMES:
                self.talking = False
                self.frame_buffer.clear()
                print("\n[END TALKING]")
                if self.current_clip:
                    audio = np.concatenate(self.current_clip)
                    self.current_clip = []
                    return audio

        self.frame_buffer.append(mono.copy())
        return None


async def main():
    load_environment()
    transcriber = Transcriber()
    client = await Client.connect(LOCAL_HOST)

    try:
        await client.start_workflow(
            ChatAgentWorkflow.run,
            id=WF_ID,
            task_queue=TASK_QUEUE,
        )
        print("Workflow started:", WF_ID)
    except WorkflowAlreadyStartedError:
        print("Workflow already running:", WF_ID)
    except Exception as exc:
        print(f"Failed to start workflow: {exc}")
        return

    handle = client.get_workflow_handle(WF_ID)

    audio_queue: queue.Queue[np.ndarray] = queue.Queue()
    segmenter = SpeechSegmenter()

    print("Listening... (Ctrl+C to stop)")

    def callback(indata, frames, time_info, status):
        if status:
            pass

        mono = indata[:, 0]
        audio = segmenter.process_frame(mono)
        if audio is not None:
            audio_queue.put(audio)

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
                normalized = text.strip().lower().strip(" .,!?:;\"'")
                if normalized in {"quit", "exit", "stop"}:
                    print("[INFO] Quit requested. Summarizing session.")
                    await handle.signal(ChatAgentWorkflow.request_shutdown)
                    break
                await handle.signal(ChatAgentWorkflow.new_text_input, text)
            else:
                print("\n[WARN] No speech recognized.")


if __name__ == "__main__":
    asyncio.run(main())
