import time
import collections
import numpy as np
import sounddevice as sd
import webrtcvad

# ===== 設定 =====
SAMPLE_RATE = 16000  # webrtcvadは 8000/16000/32000/48000 が推奨
FRAME_MS = 30  # 10, 20, 30ms のどれか
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)
VAD_MODE = 2  # 0(ゆるい)〜3(厳しい)
START_TRIGGER_FRAMES = 8  # 連続で「音声」判定がこれ以上で "talking" 開始
END_TRIGGER_FRAMES = 12  # 連続で「無音」判定がこれ以上で "talking" 終了

vad = webrtcvad.Vad(VAD_MODE)


def frame_is_speech(frame_f32: np.ndarray) -> bool:
    """
    sounddeviceはfloat32(-1..1)で来るので int16 PCM に変換してVADへ
    """
    pcm16 = (np.clip(frame_f32, -1.0, 1.0) * 32767).astype(np.int16)
    return vad.is_speech(pcm16.tobytes(), SAMPLE_RATE)


def main():
    speech_hist = collections.deque(
        maxlen=max(START_TRIGGER_FRAMES, END_TRIGGER_FRAMES)
    )
    talking = False
    speech_streak = 0
    silence_streak = 0

    print("Listening... (Ctrl+C to stop)")

    def callback(indata, frames, time_info, status):
        nonlocal talking, speech_streak, silence_streak

        if status:
            # ここはログだけ（必要なら）
            pass

        # indata shape: (frames, channels) -> モノラル化
        mono = indata[:, 0]

        is_speech = frame_is_speech(mono)

        if is_speech:
            speech_streak += 1
            silence_streak = 0
        else:
            silence_streak += 1
            speech_streak = 0

        # ---- 状態遷移 ----
        if not talking and speech_streak >= START_TRIGGER_FRAMES:
            talking = True
            print("\n[START TALKING]")
            # ここで「話し始めた」時にやりたい処理を開始してもOK

        if talking:
            # 「話している間」の処理（ここがあなたの“やりたいこと”）
            # 例: 何かの処理をする/録音バッファに貯める/別スレッドを起動など
            print(".", end="", flush=True)

            if silence_streak >= END_TRIGGER_FRAMES:
                talking = False
                print("\n[END TALKING]")
                # ここで「話し終わった」時の処理（例: バッファ確定など）

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=FRAME_SAMPLES,
        callback=callback,
    ):
        while True:
            # “話していない時は何もしない”の部分：
            # コールバックが音を見てくれて、ここは寝てるだけ
            time.sleep(0.1)


if __name__ == "__main__":
    main()
