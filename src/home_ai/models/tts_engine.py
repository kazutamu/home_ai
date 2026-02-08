import os
from typing import Iterable, Tuple

import numpy as np
from TTS.api import TTS

TTS_MODEL_NAME = "tts_models/en/vctk/vits"


class TextToSpeech:
    """Wraps TTS initialization and synthesis."""

    def __init__(self, model_name: str = TTS_MODEL_NAME) -> None:
        model_name = os.environ.get("HOME_AI_TTS_MODEL", model_name)
        self.model_name = model_name
        self.tts = TTS(model_name)

    def synthesize(self, text: str) -> Tuple[list[float], int]:
        if "xtts" in self.model_name.lower():
            speaker_wav = os.environ.get("HOME_AI_TTS_COQUI_SPEAKER_WAV")
            language = os.environ.get("HOME_AI_TTS_COQUI_LANGUAGE", "en")
            if not speaker_wav:
                raise ValueError("HOME_AI_TTS_COQUI_SPEAKER_WAV is required for XTTS.")
            wav = self.tts.tts(text=text, speaker_wav=speaker_wav, language=language)
        else:
            wav = self.tts.tts(text=text, speaker="p231")
        # Temporal's default JSON converter cannot serialize numpy scalars (e.g. float32)
        # so force to plain Python floats.
        wav_list = np.asarray(wav, dtype=float).tolist()
        return wav_list, int(self.tts.synthesizer.output_sample_rate)

    def supports_streaming(self) -> bool:
        model = getattr(self.tts.synthesizer, "tts_model", None)
        return model is not None and hasattr(model, "inference_stream")

    def output_sample_rate(self) -> int:
        return int(self.tts.synthesizer.output_sample_rate)

    def stream(
        self, text: str, *, speaker_wav: str, language: str
    ) -> Iterable[np.ndarray]:
        model = self.tts.synthesizer.tts_model
        config = model.config
        gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(
            speaker_wav,
            max_ref_length=config.max_ref_len,
            gpt_cond_len=config.gpt_cond_len,
            gpt_cond_chunk_len=config.gpt_cond_chunk_len,
            sound_norm_refs=config.sound_norm_refs,
        )
        for chunk in model.inference_stream(
            text,
            language,
            gpt_cond_latent,
            speaker_embedding,
        ):
            yield chunk.detach().cpu().numpy()
