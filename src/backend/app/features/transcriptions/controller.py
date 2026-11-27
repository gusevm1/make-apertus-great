from fastapi import APIRouter, Depends, UploadFile

from app.core.auth import require_user
from app.core.uploads import size_limited_route
from app.features.transcriptions.dependencies import TranscriptionServiceDep
from app.features.transcriptions.schemas import (
    WAV_MAX_BYTES,
    WAV_TOO_LARGE_MESSAGE,
    ResponseTranscription,
)

router = APIRouter(
    prefix="/transcriptions",
    tags=["transcriptions"],
    dependencies=[Depends(require_user)],
    route_class=size_limited_route(max_bytes=WAV_MAX_BYTES, message=WAV_TOO_LARGE_MESSAGE),
)


@router.post("", response_model=ResponseTranscription)
async def create_transcription(
    file: UploadFile, service: TranscriptionServiceDep
) -> ResponseTranscription:
    """Transcribe one WAV recording (at most 60 seconds and 5 MB); nothing is stored."""
    # One byte over the limit is enough to know it is too large.
    wav = await file.read(WAV_MAX_BYTES + 1)
    transcription = await service.create_transcription(wav=wav)
    return ResponseTranscription.model_validate(transcription, from_attributes=True)
