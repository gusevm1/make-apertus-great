import { useRef, useState } from "react";
import { api } from "./api";
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
  const [error, setError] = useState<string | null>(null);
  const capture = useRef<AudioCapture | null>(null);
  const timer = useRef<number | undefined>(undefined);

  async function start() {
    // A second click while the permission prompt is open must not start a second capture.
    if (phase !== "idle") return;
    setError(null);
    setPhase("starting");
    try {
      capture.current = await startAudioCapture();
    } catch {
      setError("Could not start the microphone. Check that it is allowed.");
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
    try {
      const form = new FormData();
      const wav = new Blob([await recording.stop()], { type: "audio/wav" });
      form.append("file", wav, "recording.wav");
      const result = await api<{ text: string }>("/api/transcriptions", token, {
        method: "POST",
        body: form,
      });
      if (result.text.trim() === "") setError("No speech was recognised.");
      else onTranscript(result.text);
    } catch (transcribeError) {
      setError(
        transcribeError instanceof Error
          ? transcribeError.message
          : "Could not transcribe the recording.",
      );
    }
    setPhase("idle");
  }

  return { phase, error, start, stop };
}
