import io
import wave

from app.clients.apertus import ApertusClient, Model
from app.core.errors import PayloadTooLargeError, UnsupportedMediaTypeError
from app.features.transcriptions.prompts import transcription_instruction
from app.features.transcriptions.schemas import (
    WAV_MAX_BYTES,
    WAV_MAX_SECONDS,
    WAV_TOO_LARGE_MESSAGE,
    Transcription,
)


class TranscriptionService:
    def __init__(self, apertus: ApertusClient) -> None:
        self.apertus = apertus

    async def create_transcription(self, wav: bytes) -> Transcription:
        """Turn a WAV recording into the words spoken in it."""
        if len(wav) > WAV_MAX_BYTES:
            raise PayloadTooLargeError(WAV_TOO_LARGE_MESSAGE)
        seconds = wav_seconds(wav=wav)
        if seconds is None:
            raise UnsupportedMediaTypeError("Only WAV audio can be transcribed.")
        if seconds > WAV_MAX_SECONDS:
            raise PayloadTooLargeError(
                f"The recording is {seconds:.0f} seconds long. "
                f"Send at most {WAV_MAX_SECONDS} seconds."
            )
        result = await self.apertus.transcribe(
            wav=wav,
            instruction=transcription_instruction(),
            model=Model.SMART,
            purpose="transcribe",
        )
        return Transcription(
            text=result.content.strip(), model=result.model, latency_ms=result.latency_ms
        )


def wav_seconds(wav: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(wav)) as recording:
            return recording.getnframes() / recording.getframerate()
    except (wave.Error, EOFError, ZeroDivisionError):
        return None
