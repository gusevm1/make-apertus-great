from typing import Annotated, Any
from uuid import UUID, uuid5

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.clients.banking import BankingClientDep
from app.core.config import get_settings
from app.core.errors import ForbiddenError, UnauthorizedError

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# ponytail: owner columns stay UUIDs, derived from the customer id, so nothing else changes
CUSTOMER_NAMESPACE = UUID("6f1d3c0a-8a55-4c0e-9d53-0d6f6d2b7a11")

bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: UUID
    customer_id: str
    token: str
    # The banking API's /customer, read once per request here; the chat's context uses it.
    profile: dict[str, Any]


def owner_id(customer_id: str) -> UUID:
    return uuid5(CUSTOMER_NAMESPACE, customer_id)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    banking: BankingClientDep,
) -> CurrentUser:
    """The customer the token belongs to, as the banking API says, never as the browser says."""
    if credentials is None:
        raise UnauthorizedError("Open the TrustRoom from the e-banking")
    # ponytail: one call to the banking API per request; cache per token if it gets slow
    customer = await banking.get(path="/customer", token=credentials.credentials)
    customer_id = customer["customer_id"]
    return CurrentUser(
        id=owner_id(customer_id=customer_id),
        customer_id=customer_id,
        token=credentials.credentials,
        profile=customer,
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


async def require_user(_: CurrentUserDep) -> None:
    return None


async def require_allowed_origin(request: Request) -> None:
    # Browsers send Origin with every write; without one it is curl or the evals, not a site.
    origin = request.headers.get("origin")
    if request.method in SAFE_METHODS or origin is None:
        return
    if origin != get_settings().app_origin:
        raise ForbiddenError(f"Requests from {origin} are not allowed")
