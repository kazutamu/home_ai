import asyncio

from .input import InputEvent, InputEventType, InputSource, run_input_source


class TextInputSource(InputSource):
    async def events(self):
        while True:
            text = await asyncio.to_thread(input, "Enter text (or 'q' to quit): ")
            text = text.strip()
            if text.lower() == "q":
                print("Exiting.")
                yield InputEvent(InputEventType.SHUTDOWN)
                break
            yield InputEvent(InputEventType.TEXT, text=text)


async def main():
    await run_input_source(TextInputSource())


if __name__ == "__main__":
    asyncio.run(main())
