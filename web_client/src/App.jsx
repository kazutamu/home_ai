import React, { useEffect, useRef, useState } from "react";

const DEFAULT_SAMPLE_RATE = 16000;
const MIC_TARGET_RATE = 16000;

function resampleLinear(input, inRate, outRate) {
  if (inRate === outRate) {
    return input;
  }
  const ratio = outRate / inRate;
  const outputLength = Math.max(1, Math.floor(input.length * ratio));
  const output = new Float32Array(outputLength);
  for (let i = 0; i < outputLength; i++) {
    const sourceIndex = i / ratio;
    const i0 = Math.floor(sourceIndex);
    const i1 = Math.min(i0 + 1, input.length - 1);
    const frac = sourceIndex - i0;
    output[i] = input[i0] + (input[i1] - input[i0]) * frac;
  }
  return output;
}

function mergeFloat32(chunks) {
  const total = chunks.reduce((acc, chunk) => acc + chunk.length, 0);
  const merged = new Float32Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function encodeWavPcm16(samples, sampleRate) {
  const bytesPerSample = 2;
  const blockAlign = bytesPerSample;
  const byteRate = sampleRate * blockAlign;
  const dataSize = samples.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  const writeAscii = (offset, text) => {
    for (let i = 0; i < text.length; i++) {
      view.setUint8(offset + i, text.charCodeAt(i));
    }
  };

  writeAscii(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeAscii(8, "WAVE");
  writeAscii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  writeAscii(36, "data");
  view.setUint32(40, dataSize, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    const value = s < 0 ? s * 0x8000 : s * 0x7fff;
    view.setInt16(offset, value, true);
    offset += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
}

async function extractErrorMessage(resp, fallback) {
  const contentType = (resp.headers.get("content-type") || "").toLowerCase();
  if (contentType.includes("application/json")) {
    const data = await resp.json().catch(() => ({}));
    const message = data.detail || data.error || data.message;
    if (typeof message === "string" && message.trim()) {
      return message.trim();
    }
  } else {
    const text = await resp.text().catch(() => "");
    if (text.trim()) {
      return text.trim().slice(0, 200);
    }
  }
  return `${fallback} (HTTP ${resp.status})`;
}

function useAudioStream() {
  const audioCtxRef = useRef(null);
  const processorRef = useRef(null);
  const readerRef = useRef(null);
  const pendingRef = useRef([]);
  const abortRef = useRef(null);
  const levelRef = useRef(0);
  const [status, setStatus] = useState("stopped");
  const [sampleRate, setSampleRate] = useState(DEFAULT_SAMPLE_RATE);

  const enqueue = (data) => {
    pendingRef.current.push({ data, offset: 0 });
  };

  const setupAudio = () => {
    if (audioCtxRef.current) {
      return audioCtxRef.current;
    }
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const processor = audioCtx.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (event) => {
      const out = event.outputBuffer.getChannelData(0);
      out.fill(0);
      const pending = pendingRef.current;
      if (!pending.length) {
        return;
      }
      let offset = 0;
      while (pending.length && offset < out.length) {
        const current = pending[0];
        const remaining = current.data.length - current.offset;
        const toCopy = Math.min(remaining, out.length - offset);
        out.set(current.data.subarray(current.offset, current.offset + toCopy), offset);
        current.offset += toCopy;
        offset += toCopy;
        if (current.offset >= current.data.length) {
          pending.shift();
        }
      }
    };
    processor.connect(audioCtx.destination);
    audioCtxRef.current = audioCtx;
    processorRef.current = processor;
    return audioCtx;
  };

  const start = async () => {
    if (status === "streaming" || status === "connecting") {
      return;
    }
    setStatus("connecting");
    const audioCtx = setupAudio();
    try {
      await audioCtx.resume();
    } catch (err) {
      setStatus("stopped");
      throw err;
    }

    const abortController = new AbortController();
    abortRef.current = abortController;

    const resp = await fetch("/audio/stream", { signal: abortController.signal });
    if (!resp.ok) {
      setStatus("stopped");
      throw new Error(`Stream error: ${resp.status}`);
    }

    const headerRate = resp.headers.get("X-Audio-Sample-Rate");
    const inputRate = headerRate ? parseInt(headerRate, 10) : DEFAULT_SAMPLE_RATE;
    setSampleRate(inputRate);
    setStatus("streaming");

    const reader = resp.body.getReader();
    readerRef.current = reader;
    let leftover = new Uint8Array(0);
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        if (!value || value.length === 0) {
          continue;
        }
        let data = value;
        if (leftover.length) {
          const merged = new Uint8Array(leftover.length + data.length);
          merged.set(leftover, 0);
          merged.set(data, leftover.length);
          data = merged;
          leftover = new Uint8Array(0);
        }
        if (data.length % 2 === 1) {
          leftover = data.slice(data.length - 1);
          data = data.slice(0, data.length - 1);
        }
        if (!data.length) {
          continue;
        }
        const samples = new Int16Array(data.buffer, data.byteOffset, data.byteLength / 2);
        const floats = new Float32Array(samples.length);
        for (let i = 0; i < samples.length; i++) {
          floats[i] = samples[i] / 32768;
        }
        let sum = 0;
        for (let i = 0; i < floats.length; i++) {
          const v = floats[i];
          sum += v * v;
        }
        const rms = Math.sqrt(sum / Math.max(1, floats.length));
        const scaled = Math.min(1, rms * 6);
        levelRef.current = levelRef.current * 0.85 + scaled * 0.15;
        const resampled = resampleLinear(floats, inputRate, audioCtx.sampleRate);
        enqueue(resampled);
      }
    } finally {
      setStatus("stopped");
    }
  };

  const stop = async () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus("stopped");
    pendingRef.current = [];
  };

  useEffect(() => () => {
    stop();
    processorRef.current?.disconnect();
    audioCtxRef.current?.close();
  }, []);

  return {
    status,
    sampleRate,
    levelRef,
    start,
    stop
  };
}

function useMicRecorder() {
  const [status, setStatus] = useState("idle");
  const levelRef = useRef(0);
  const chunksRef = useRef([]);
  const audioCtxRef = useRef(null);
  const streamRef = useRef(null);
  const sourceRef = useRef(null);
  const processorRef = useRef(null);

  const startRecording = async () => {
    if (status !== "idle") {
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    await audioCtx.resume();

    chunksRef.current = [];
    streamRef.current = stream;
    audioCtxRef.current = audioCtx;

    const source = audioCtx.createMediaStreamSource(stream);
    const processor = audioCtx.createScriptProcessor(4096, 1, 1);

    processor.onaudioprocess = (event) => {
      const channel = event.inputBuffer.getChannelData(0);
      chunksRef.current.push(new Float32Array(channel));

      let sum = 0;
      for (let i = 0; i < channel.length; i++) {
        const v = channel[i];
        sum += v * v;
      }
      const rms = Math.sqrt(sum / Math.max(1, channel.length));
      const scaled = Math.min(1, rms * 8);
      levelRef.current = levelRef.current * 0.82 + scaled * 0.18;
    };

    source.connect(processor);
    processor.connect(audioCtx.destination);
    sourceRef.current = source;
    processorRef.current = processor;
    setStatus("recording");
  };

  const stopRecording = async () => {
    if (status !== "recording") {
      return null;
    }
    setStatus("processing");

    sourceRef.current?.disconnect();
    processorRef.current?.disconnect();
    streamRef.current?.getTracks().forEach((track) => track.stop());

    const audioCtx = audioCtxRef.current;
    const inputRate = audioCtx?.sampleRate || MIC_TARGET_RATE;
    if (audioCtx) {
      await audioCtx.close();
    }

    sourceRef.current = null;
    processorRef.current = null;
    streamRef.current = null;
    audioCtxRef.current = null;

    const merged = mergeFloat32(chunksRef.current);
    chunksRef.current = [];

    if (!merged.length) {
      setStatus("idle");
      return null;
    }

    const resampled = resampleLinear(merged, inputRate, MIC_TARGET_RATE);
    const blob = encodeWavPcm16(resampled, MIC_TARGET_RATE);

    setStatus("idle");
    levelRef.current = 0;
    return blob;
  };

  useEffect(() => () => {
    sourceRef.current?.disconnect();
    processorRef.current?.disconnect();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    audioCtxRef.current?.close();
  }, []);

  return {
    status,
    levelRef,
    startRecording,
    stopRecording
  };
}

export default function App() {
  const [text, setText] = useState("");
  const [log, setLog] = useState([]);
  const [sending, setSending] = useState(false);
  const [speakerLevel, setSpeakerLevel] = useState(0);
  const [micLevel, setMicLevel] = useState(0);

  const { status, sampleRate, levelRef, start, stop } = useAudioStream();
  const {
    status: micStatus,
    levelRef: micLevelRef,
    startRecording,
    stopRecording
  } = useMicRecorder();

  useEffect(() => {
    const id = setInterval(() => {
      setSpeakerLevel(levelRef.current);
      setMicLevel(micLevelRef.current);
    }, 80);
    return () => clearInterval(id);
  }, [levelRef, micLevelRef]);

  const addLog = (message) => {
    const ts = new Date().toLocaleTimeString();
    setLog((prev) => [`[${ts}] ${message}`, ...prev].slice(0, 12));
  };

  const sendText = async () => {
    const payload = text.trim();
    if (!payload) {
      return;
    }
    setSending(true);
    try {
      const resp = await fetch("/input", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: payload })
      });
      if (!resp.ok) {
        const message = await extractErrorMessage(resp, "Failed to send");
        throw new Error(message);
      }
      addLog(`Sent: ${payload}`);
      setText("");
    } catch (err) {
      addLog(`Send failed: ${err.message || err}`);
    } finally {
      setSending(false);
    }
  };

  const onMicButton = async () => {
    try {
      if (micStatus === "idle") {
        await startRecording();
        addLog("Voice capture started");
        return;
      }
      if (micStatus !== "recording") {
        return;
      }

      const blob = await stopRecording();
      if (!blob) {
        addLog("No voice detected");
        return;
      }

      const formData = new FormData();
      formData.append("audio", blob, "voice.wav");

      const resp = await fetch("/voice/transcribe", {
        method: "POST",
        body: formData
      });
      if (!resp.ok) {
        const message = await extractErrorMessage(resp, "Transcription failed");
        throw new Error(message);
      }
      const data = await resp.json().catch(() => ({}));

      const transcript = (data.text || "").trim();
      if (!transcript) {
        addLog("No speech recognized");
        return;
      }

      setText((prev) => (prev ? `${prev} ${transcript}` : transcript));
      addLog(`Voice transcript: ${transcript}`);
    } catch (err) {
      addLog(`Voice input failed: ${err.message || err}`);
    }
  };

  return (
    <div className="page">
      <div className="card">
        <header>
          <h1>Home AI</h1>
          <p>Type or record your voice, then send a message and listen to streamed replies.</p>
        </header>

        <div className="row">
          <input
            type="text"
            placeholder="Ask anything..."
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                sendText();
              }
            }}
          />
          <button onClick={sendText} disabled={sending}>Send</button>
        </div>

        <div className="row">
          <button
            className={micStatus === "recording" ? "danger" : "secondary"}
            onClick={onMicButton}
            disabled={micStatus === "processing"}
          >
            {micStatus === "recording" ? "Stop Voice" : micStatus === "processing" ? "Processing..." : "Record Voice"}
          </button>
          <div className="status">Mic: {micStatus}</div>
        </div>

        <div className="row">
          <button
            className="secondary"
            onClick={status === "streaming" ? stop : start}
          >
            {status === "streaming" ? "Stop Audio" : "Start Audio"}
          </button>
          <div className="status">
            Audio: {status}
            {status === "streaming" ? ` (${sampleRate} Hz)` : ""}
          </div>
        </div>

        <div className="meter">
          <div className="meter-label">Speaker</div>
          <div className="meter-value">{Math.round(speakerLevel * 100)}%</div>
          <div className="meter-bar">
            <div
              className="meter-fill"
              style={{ width: `${Math.min(1, speakerLevel) * 100}%` }}
            />
          </div>
        </div>

        <div className="meter">
          <div className="meter-label">Mic</div>
          <div className="meter-value">{Math.round(micLevel * 100)}%</div>
          <div className="meter-bar">
            <div
              className="meter-fill"
              style={{ width: `${Math.min(1, micLevel) * 100}%` }}
            />
          </div>
        </div>

        <div className="log">
          {log.length ? log.join("\n") : "No messages yet."}
        </div>
      </div>
    </div>
  );
}
