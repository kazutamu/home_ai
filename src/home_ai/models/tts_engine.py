from typing import Tuple

import numpy as np
from TTS.api import TTS

from ..config import TTS_MODEL_NAME


class TextToSpeech:
    """Wraps TTS initialization and synthesis."""

    def __init__(self, model_name: str = TTS_MODEL_NAME) -> None:
        self.tts = TTS(model_name)

    def synthesize(self, text: str) -> Tuple[list[float], int]:
        wav = self.tts.tts(text=text)
        # Temporal's default JSON converter cannot serialize numpy scalars (e.g. float32)
        # so force to plain Python floats.
        wav_list = np.asarray(wav, dtype=float).tolist()
        return wav_list, int(self.tts.synthesizer.output_sample_rate)
