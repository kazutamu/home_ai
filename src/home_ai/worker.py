import asyncio

from .web.server import main as server_main


async def main():
    await asyncio.to_thread(server_main)


if __name__ == "__main__":
    asyncio.run(main())
