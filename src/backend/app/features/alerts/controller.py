from fastapi import APIRouter, Depends

from app.core.auth import CurrentUserDep, require_user
from app.features.alerts.dependencies import AlertServiceDep, OwnedDismissalDep
from app.features.alerts.schemas import (
    AlertKind,
    RequestAlertDismissalCreate,
    RequestAlertSettingUpdate,
    ResponseAlert,
    ResponseAlertDismissal,
    ResponseAlertSetting,
)

router = APIRouter(tags=["alerts"], dependencies=[Depends(require_user)])


@router.get("/alerts", response_model=list[ResponseAlert])
async def list_alerts(user: CurrentUserDep, service: AlertServiceDep) -> list[ResponseAlert]:
    """The flags that need the customer's attention now."""
    alerts = await service.list_alerts(owner_id=user.id, token=user.token)
    return [ResponseAlert.model_validate(alert, from_attributes=True) for alert in alerts]


@router.get("/alert-dismissals", response_model=list[ResponseAlertDismissal])
async def list_alert_dismissals(
    user: CurrentUserDep, service: AlertServiceDep
) -> list[ResponseAlertDismissal]:
    """The flags the customer marked done."""
    dismissals = await service.list_dismissals(owner_id=user.id)
    return [ResponseAlertDismissal.model_validate(row, from_attributes=True) for row in dismissals]


@router.post("/alert-dismissals", response_model=ResponseAlertDismissal, status_code=201)
async def create_alert_dismissal(
    body: RequestAlertDismissalCreate, user: CurrentUserDep, service: AlertServiceDep
) -> ResponseAlertDismissal:
    """Mark one flag done, so it no longer shows."""
    dismissal = await service.create_dismissal(owner_id=user.id, key=body.key)
    return ResponseAlertDismissal.model_validate(dismissal, from_attributes=True)


@router.delete("/alert-dismissals/{dismissal_id}", status_code=204)
async def delete_alert_dismissal(dismissal: OwnedDismissalDep, service: AlertServiceDep) -> None:
    """Show the flag again while it is still open."""
    await service.delete_dismissal(dismissal_id=dismissal.id)


@router.get("/alert-settings", response_model=list[ResponseAlertSetting])
async def list_alert_settings(
    user: CurrentUserDep, service: AlertServiceDep
) -> list[ResponseAlertSetting]:
    """Every check and whether it is on."""
    settings = await service.list_settings(owner_id=user.id)
    return [ResponseAlertSetting.model_validate(row, from_attributes=True) for row in settings]


@router.patch("/alert-settings/{kind}", response_model=ResponseAlertSetting)
async def update_alert_setting(
    kind: AlertKind,
    body: RequestAlertSettingUpdate,
    user: CurrentUserDep,
    service: AlertServiceDep,
) -> ResponseAlertSetting:
    """Turn a check on or off."""
    setting = await service.update_setting(owner_id=user.id, kind=kind, enabled=body.enabled)
    return ResponseAlertSetting.model_validate(setting, from_attributes=True)


@router.delete("/alert-settings/{kind}", status_code=204)
async def delete_alert_setting(
    kind: AlertKind, user: CurrentUserDep, service: AlertServiceDep
) -> None:
    """Put a check back to its default."""
    await service.delete_setting(owner_id=user.id, kind=kind)
