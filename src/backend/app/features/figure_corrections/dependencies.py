from typing import Annotated

from fastapi import Depends

from app.clients.apertus import ApertusClientDep
from app.features.figure_corrections.service import FigureCorrectionService


def get_figure_correction_service(apertus: ApertusClientDep) -> FigureCorrectionService:
    return FigureCorrectionService(apertus=apertus)


FigureCorrectionServiceDep = Annotated[
    FigureCorrectionService, Depends(get_figure_correction_service)
]
