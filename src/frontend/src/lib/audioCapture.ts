import { encodeWav } from "./wav";

const TARGET_SAMPLE_RATE = 16_000;
// Below the 8 kHz Nyquist limit of the target rate, so downsampling does not alias.
const LOWPASS_HZ = 7_200;
// The meter spans quiet room noise to loud speech.
const LEVEL_FLOOR_DB = -60;
const LEVEL_RANGE_DB = 50;
const LEVEL_DECAY = 0.9;
const WORKLET_NAME = "pcm-capture";
const WORKLET_SOURCE = `registerProcessor("${WORKLET_NAME}", class extends AudioWorkletProcessor {
  process([input]) {
    if (input[0] !== undefined) this.port.postMessage(input[0].slice());
    return true;
  }
});`;

export interface AudioCapture {
  /** The latest input level between 0 and 1. */
  level: () => number;
  /** Ends the recording and returns it as 16 kHz mono WAV. */
  stop: () => Promise<ArrayBuffer>;
  cancel: () => void;
}

export function canCaptureAudio(): boolean {
  return (
    navigator.mediaDevices?.getUserMedia !== undefined &&
    typeof AudioWorkletNode !== "undefined"
  );
}

async function resample({
  chunks,
  sampleRate,
}: {
  chunks: Float32Array<ArrayBuffer>[];
  sampleRate: number;
}): Promise<Float32Array> {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  if (length === 0) return new Float32Array();
  const offline = new OfflineAudioContext(
    1,
    Math.ceil((length * TARGET_SAMPLE_RATE) / sampleRate),
    TARGET_SAMPLE_RATE,
  );
  const buffer = offline.createBuffer(1, length, sampleRate);
  let offset = 0;
  for (const chunk of chunks) {
    buffer.copyToChannel(chunk, 0, offset);
    offset += chunk.length;
  }
  const source = offline.createBufferSource();
  source.buffer = buffer;
  source.connect(offline.destination);
  source.start();
  return (await offline.startRendering()).getChannelData(0);
}

/** Asks for the microphone and records from it until `stop` or `cancel`. */
export async function startAudioCapture(): Promise<AudioCapture> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const context = new AudioContext();
  const chunks: Float32Array<ArrayBuffer>[] = [];
  let level = 0;

  function release() {
    stream.getTracks().forEach((track) => track.stop());
    void context.close();
  }

  try {
    const moduleUrl = URL.createObjectURL(
      new Blob([WORKLET_SOURCE], { type: "text/javascript" }),
    );
    await context.audioWorklet.addModule(moduleUrl);
    URL.revokeObjectURL(moduleUrl);
    const lowpass = new BiquadFilterNode(context, {
      type: "lowpass",
      frequency: LOWPASS_HZ,
    });
    const worklet = new AudioWorkletNode(context, WORKLET_NAME, {
      channelCount: 1,
      channelCountMode: "explicit",
    });
    worklet.port.onmessage = ({
      data,
    }: MessageEvent<Float32Array<ArrayBuffer>>) => {
      chunks.push(data);
      const rms = Math.sqrt(
        data.reduce((sum, sample) => sum + sample * sample, 0) / data.length,
      );
      const decibels = 20 * Math.log10(Math.max(rms, 1e-6));
      const loudness = (decibels - LEVEL_FLOOR_DB) / LEVEL_RANGE_DB;
      level = Math.max(Math.min(1, loudness), level * LEVEL_DECAY);
    };
    context.createMediaStreamSource(stream).connect(lowpass).connect(worklet);
    // The worklet outputs silence; the connection keeps it processing.
    worklet.connect(context.destination);
    await context.resume();
  } catch (error) {
    release();
    throw error;
  }

  return {
    level: () => level,
    cancel: release,
    stop: async () => {
      release();
      const samples = await resample({
        chunks,
        sampleRate: context.sampleRate,
      });
      return encodeWav({ samples, sampleRate: TARGET_SAMPLE_RATE });
    },
  };
}
