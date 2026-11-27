from fastapi import APIRouter, Depends

from app.core.auth import require_user
from app.features.widgets.dependencies import OwnedWidgetDep, WidgetServiceDep
from app.features.widgets.schemas import Form, ResponseWidgetVersion

router = APIRouter(prefix="/widgets", tags=["widgets"], dependencies=[Depends(require_user)])


@router.get("/{widget_id}/versions/{version_number}", response_model=ResponseWidgetVersion)
async def get_widget_version(
    version_number: int, widget: OwnedWidgetDep, service: WidgetServiceDep, form: Form = "live"
) -> ResponseWidgetVersion:
    """One version of your widget as a page: `live` for the canvas, `static` with SVG charts."""
    version, html = await service.render_version(
        widget=widget, version_number=version_number, form=form
    )
    return ResponseWidgetVersion(
        widget_id=widget.id,
        number=version.number,
        title=widget.title,
        html=html,
        model=version.model,
        latency_ms=version.latency_ms,
        checks=version.checks,
        created_at=version.created_at,
    )
