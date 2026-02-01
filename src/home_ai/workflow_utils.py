from datetime import timedelta
from typing import Optional

from temporalio import workflow


async def interrupt_speech(handle: workflow.ActivityHandle) -> None:
    handle.cancel()
    try:
        await workflow.execute_local_activity(
            "stop_audio",
            start_to_close_timeout=timedelta(seconds=5),
        )
    except Exception:
        pass


async def cleanup_audio_file(path: Optional[str]) -> None:
    if not path:
        return
    try:
        await workflow.execute_local_activity(
            "cleanup_audio_file",
            path,
            start_to_close_timeout=timedelta(seconds=5),
        )
    except Exception:
        pass
