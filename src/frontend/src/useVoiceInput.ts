import { useRef, useState } from "react";
import { api, type Failure, requestErrorOf } from "./api";
import { type AudioCapture, startAudioCapture } from "./lib/audioCapture";

// The backend takes at most 60 seconds per recording.
const RECORDING_MAX_MS = 60_000;

type Phase = "idle" | "starting" | "recording" | "transcribing";

/** Records from the microphone and hands the transcribed text to `onTranscript`. */
export function useVoiceInput({
  token,
  onTranscript,
}: {
  token: string;
  onTranscript: (text: string) => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [failure, setFailure] = useState<Failure | null>(null);
  const capture = useRef<AudioCapture | null>(null);
  const timer = useRef<number | undefined>(undefined);
  // A recording whose transcription failed, sent again by Try again.
  const failedRecording = useRef<Blob | null>(null);

  async function start() {
    // A second click while the permission prompt is open must not start a second capture.
    if (phase !== "idle") return;
    setFailure(null);
    failedRecording.current = null;
    setPhase("starting");
    try {
      capture.current = await startAudioCapture();
    } catch {
      setFailure({
        title: "Could not start the microphone.",
        detail: "Check that it is allowed.",
      });
      setPhase("idle");
      return;
    }
    setPhase("recording");
    timer.current = window.setTimeout(() => void stop(), RECORDING_MAX_MS);
  }

  async function stop() {
    window.clearTimeout(timer.current);
    const recording = capture.current;
    if (recording === null) return;
    capture.current = null;
    setPhase("transcribing");
    let wav: Blob;
    try {
      wav = new Blob([await recording.stop()], { type: "audio/wav" });
    } catch {
      setFailure({
        title: "The recording failed.",
        detail: "Nothing was added to the input.",
      });
      setPhase("idle");
      return;
    }
    await transcribe(wav);
  }

  async function transcribe(wav: Blob) {
    setPhase("transcribing");
    setFailure(null);
    failedRecording.current = null;
    try {
      const form = new FormData();
      form.append("file", wav, "recording.wav");
      const result = await api<{ text: string }>("/api/transcriptions", token, {
        method: "POST",
        body: form,
      });
      if (result.text.trim() === "") {
        setFailure({
          title: "No speech was recognised.",
          detail: "Nothing was added to the input.",
        });
      } else onTranscript(result.text);
    } catch (error) {
      failedRecording.current = wav;
      setFailure({
        title: requestErrorOf(error).message,
        detail: "Your recording was kept.",
      });
    }
    setPhase("idle");
  }

  /** Sends a failed recording again, or records anew. */
  function retry() {
    const wav = failedRecording.current;
    if (wav === null) void start();
    else void transcribe(wav);
  }

  return { phase, failure, start, stop, retry };
}
