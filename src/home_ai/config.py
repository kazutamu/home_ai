from __future__ import annotations

from dotenv import load_dotenv


def load_environment() -> None:
    """Load .env if present; OS env vars still take precedence."""
    load_dotenv()
