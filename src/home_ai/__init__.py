"""
Keep package import lightweight so Temporal workflow sandbox doesn't pull in
non-deterministic deps (e.g., httpx via ollama) when loading workflows.
Lazy-load exports on demand instead of at import time.
"""

__all__ = ["main", "play_audio", "record_until_enter", "SAMPLE_RATE", "PLAYBACK_SPEED"]


def __getattr__(name):
    if name == "main":
        from .main import main

        return main
    if name == "play_audio":
        from .audio import play_audio

        return play_audio
    if name == "record_until_enter":
        from .audio import record_until_enter

        return record_until_enter
    if name == "SAMPLE_RATE":
        from .config import SAMPLE_RATE

        return SAMPLE_RATE
    if name == "PLAYBACK_SPEED":
        from .config import PLAYBACK_SPEED

        return PLAYBACK_SPEED
    raise AttributeError(name)
