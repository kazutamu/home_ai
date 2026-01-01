from .audio import play_audio, record_until_enter
from .chatbot import reply
from .config import PLAYBACK_SPEED, SAMPLE_RATE
from .models import TextToSpeech, Transcriber


def main():
    print("Press Enter to record, or type 'q' then Enter to quit.")
    transcriber = Transcriber()
    tts = TextToSpeech()

    while True:
        cmd = input("Ready? (Enter=record, q=quit): ").strip().lower()
        if cmd.startswith("q"):
            print("Exiting.")
            break

        audio = record_until_enter(samplerate=SAMPLE_RATE)
        if audio.size == 0:
            print("No audio captured, try again.")
            continue

        input_text = transcriber.transcribe(audio)
        if not input_text:
            print("Could not understand audio, try again.")
            continue

        print(f"Heard: {input_text}")
        output_text = reply(input_text)
        print(f"LLM Response: {output_text}")

        wav, output_sample_rate = tts.synthesize(output_text)
        play_audio(wav, output_sample_rate, speed=PLAYBACK_SPEED)


if __name__ == "__main__":
    main()
