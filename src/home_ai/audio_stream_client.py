import asyncio
import os

from aiohttp import ClientSession
import numpy as np
import sounddevice as sd

DEFAULT_URL = "http://localhost:8080/audio/stream"


async def main() -> None:
    url = os.environ.get("HOME_AI_AUDIO_STREAM_URL", DEFAULT_URL)
    print(f"[audio_stream_client] Connecting to {url}")
    player = os.environ.get("HOME_AI_AUDIO_STREAM_PLAYER", "sounddevice").lower()

    async with ClientSession() as session:
        async with session.get(url) as resp:
            print(f"[audio_stream_client] HTTP {resp.status}")
            print(
                "[audio_stream_client] Headers:",
                dict(resp.headers),
            )
            sample_rate = resp.headers.get("X-Audio-Sample-Rate", "16000")
            print(f"[audio_stream_client] Using sample rate: {sample_rate}")
            total_bytes = 0
            logged_first = False
            if player == "sounddevice":
                samplerate = int(sample_rate)
                print("[audio_stream_client] Starting sounddevice playback...")
                stream = sd.OutputStream(samplerate=samplerate, channels=1, dtype="float32")
                stream.start()
                leftover = b""
                try:
                    async for chunk in resp.content.iter_chunked(4096):
                        if not chunk:
                            continue
                        total_bytes += len(chunk)
                        if not logged_first:
                            print(f"[audio_stream_client] First chunk: {len(chunk)} bytes")
                            logged_first = True
                        data = leftover + chunk
                        if len(data) % 2 == 1:
                            leftover = data[-1:]
                            data = data[:-1]
                        else:
                            leftover = b""
                        if not data:
                            continue
                        audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32767.0
                        try:
                            stream.write(audio.reshape(-1, 1))
                        except Exception as exc:
                            print(f"[audio_stream_client] sounddevice error: {exc}")
                            break
                except Exception as exc:
                    print(f"[audio_stream_client] Stream error: {exc}")
                finally:
                    print(f"[audio_stream_client] Total bytes received: {total_bytes}")
                    stream.stop()
                    stream.close()
            else:
                raise RuntimeError(
                    "Unsupported HOME_AI_AUDIO_STREAM_PLAYER. Use 'sounddevice'."
                )


if __name__ == "__main__":
    asyncio.run(main())
