from temporalio import activity

from .audio import play_audio
from .chatbot import reply
from .models import TextToSpeech

PLAYBACK_SPEED = 1.25


@activity.defn(name="llm_respond")
async def llm_respond(text: str) -> str:
    return reply(text)


@activity.defn(name="speak_text")
async def speak_text(text: str) -> None:
    """Synth + play inside the activity to avoid returning large payloads."""
    tts = TextToSpeech()
    audio, sample_rate = tts.synthesize(text)
    play_audio(audio, sample_rate, speed=PLAYBACK_SPEED)
