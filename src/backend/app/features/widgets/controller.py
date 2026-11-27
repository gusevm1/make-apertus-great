from fastapi import APIRouter, Depends

from app.core.auth import CurrentUserDep, require_user
from app.features.widgets.dependencies import OwnedWidgetDep, WidgetServiceDep
from app.features.widgets.schemas import (
    Form,
    RequestWidgetPublicationCreate,
    ResponseWidgetPublication,
    ResponseWidgetVersion,
)

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
        published_version=widget.published_version,
        created_at=version.created_at,
    )


@router.post("/{widget_id}/publications", response_model=ResponseWidgetPublication, status_code=201)
async def create_widget_publication(
    body: RequestWidgetPublicationCreate,
    widget: OwnedWidgetDep,
    user: CurrentUserDep,
    service: WidgetServiceDep,
) -> ResponseWidgetPublication:
    """Put your widget's current version on your e-banking dashboard, replacing an older copy."""
    published, dashboard_id, tile_id = await service.publish_widget(
        widget=widget, dashboard_id=body.dashboard_id, token=user.token
    )
    return ResponseWidgetPublication(
        widget_id=published.id,
        version_number=published.current_version,
        dashboard_id=dashboard_id,
        dashboard_widget_id=tile_id,
    )
