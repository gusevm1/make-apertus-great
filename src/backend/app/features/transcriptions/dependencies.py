from typing import Annotated

from fastapi import Depends

from app.clients.apertus import ApertusClientDep
from app.features.transcriptions.service import TranscriptionService


def get_transcription_service(apertus: ApertusClientDep) -> TranscriptionService:
    return TranscriptionService(apertus=apertus)


TranscriptionServiceDep = Annotated[TranscriptionService, Depends(get_transcription_service)]
