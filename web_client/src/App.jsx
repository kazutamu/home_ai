import React, { useEffect, useRef, useState } from "react";

const DEFAULT_SAMPLE_RATE = 16000;

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

export default function App() {
  const [text, setText] = useState("");
  const [log, setLog] = useState([]);
  const [sending, setSending] = useState(false);
  const [level, setLevel] = useState(0);
  const { status, sampleRate, levelRef, start, stop } = useAudioStream();

  useEffect(() => {
    const id = setInterval(() => {
      setLevel(levelRef.current);
    }, 80);
    return () => clearInterval(id);
  }, [levelRef]);

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
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.error || "Failed to send");
      }
      addLog(`Sent: ${payload}`);
      setText("");
    } catch (err) {
      addLog(`Send failed: ${err.message || err}`);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="page">
      <div className="card">
        <header>
          <h1>Home AI</h1>
          <p>Real-time audio stream with a minimal React client.</p>
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
          <div className="meter-label">Level</div>
          <div className="meter-value">{Math.round(level * 100)}%</div>
          <div className="meter-bar">
            <div
              className="meter-fill"
              style={{ width: `${Math.min(1, level) * 100}%` }}
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
