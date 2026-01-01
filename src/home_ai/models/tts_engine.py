from typing import Tuple

from TTS.api import TTS

from ..config import TTS_MODEL_NAME


class TextToSpeech:
    """Wraps TTS initialization and synthesis."""

    def __init__(self, model_name: str = TTS_MODEL_NAME) -> None:
        self.tts = TTS(model_name)

    def synthesize(self, text: str) -> Tuple[list, int]:
        wav = self.tts.tts(text=text)
        return wav, self.tts.synthesizer.output_sample_rate
