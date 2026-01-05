"""
Activities run outside the Temporal workflow sandbox, so network calls (e.g. Ollama)
and other side effects belong here.
"""

from temporalio import activity

from .audio import play_audio as play_audio_out
from .chatbot import reply
from .models import TextToSpeech

PLAYBACK_SPEED = 1.25


@activity.defn(name="llm_respond")
async def llm_respond(text: str) -> str:
    return reply(text)


@activity.defn(name="speak_text")
async def speak_text(text: str) -> str:
    """Synth + play inside the activity to avoid returning large payloads."""
    tts = TextToSpeech()
    audio, sample_rate = tts.synthesize(text)
    play_audio_out(audio, sample_rate, speed=PLAYBACK_SPEED)
    return "played"
