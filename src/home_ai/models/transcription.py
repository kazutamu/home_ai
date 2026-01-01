from typing import Iterable

from faster_whisper import WhisperModel

from ..config import WHISPER_COMPUTE_TYPE, WHISPER_DEVICE, WHISPER_MODEL_NAME


class Transcriber:
    """Wraps WhisperModel initialization and transcription."""

    def __init__(
        self,
        model_name: str = WHISPER_MODEL_NAME,
        device: str = WHISPER_DEVICE,
        compute_type: str = WHISPER_COMPUTE_TYPE,
    ) -> None:
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)

    def transcribe(self, audio: Iterable[float]) -> str:
        segments, _ = self.model.transcribe(
            audio, language="en", beam_size=5, vad_filter=True
        )
        return " ".join(seg.text for seg in segments).strip()
