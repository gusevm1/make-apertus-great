from pydantic import BaseModel

WAV_MAX_BYTES = 5 * 1024 * 1024
WAV_MAX_SECONDS = 60
WAV_TOO_LARGE_MESSAGE = (
    f"The recording is larger than {WAV_MAX_BYTES // 1024 // 1024} MB. Send a shorter one."
)


class Transcription(BaseModel):
    text: str
    model: str
    latency_ms: int


class ResponseTranscription(BaseModel):
    text: str
    model: str
    latency_ms: int
