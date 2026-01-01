import asyncio
from contextlib import suppress


async def process_ai_answer(tag: str):
    print(f"[{tag}] Processing AI answer...")
    await asyncio.sleep(2)


async def wav_to_text(tag: str):
    print(f"[{tag}] Converting WAV to text...")
    await asyncio.sleep(1)


async def text_to_wav(tag: str):
    print(f"[{tag}] Converting text to WAV...")
    await asyncio.sleep(1)


async def playback(tag: str):
    try:
        print(f"[{tag}] Playing back audio...")
        await asyncio.sleep(3)
        print(f"[{tag}] Playback finished.")
    except asyncio.CancelledError:
        print(f"[{tag}] Playback interrupted by new input.")
        raise


async def handle_request(tag: str):
    await wav_to_text(tag)
    await process_ai_answer(tag)
    await text_to_wav(tag)
    await playback(tag)


async def listening_stream():
    """Simulate a stream of user speech detections."""
    for idx in range(3):
        await asyncio.sleep(2 if idx == 0 else 1.5)
        yield f"request-{idx}"


async def main():
    current_task = None
    async for tag in listening_stream():
        print(f"Listening... detected {tag}")

        if current_task and not current_task.done():
            print("New input arrived, cancelling previous pipeline...")
            current_task.cancel()
            with suppress(asyncio.CancelledError):
                await current_task

        current_task = asyncio.create_task(handle_request(tag))

    if current_task:
        await current_task


if __name__ == "__main__":
    asyncio.run(main())
