from typing import TYPE_CHECKING, Any

__all__ = ["main", "play_audio", "record_until_enter", "SAMPLE_RATE", "PLAYBACK_SPEED"]

if TYPE_CHECKING:
    # For type checkers without importing at runtime.
    from .main import PLAYBACK_SPEED, SAMPLE_RATE, main, play_audio, record_until_enter


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import main as _main

        return getattr(_main, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
