from typing import Annotated

from fastapi import Depends

from app.features.figure_checks.service import FigureCheckService


def get_figure_check_service() -> FigureCheckService:
    return FigureCheckService()


FigureCheckServiceDep = Annotated[FigureCheckService, Depends(get_figure_check_service)]
