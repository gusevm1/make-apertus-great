from dataclasses import dataclass
from string import Formatter
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel

from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.payments.schemas import (
    BankWrite,
    PaymentArgs,
    PaymentCreateArgs,
    PaymentUpdateArgs,
    StandingOrderArgs,
    StandingOrderCreateArgs,
    StandingOrderUpdateArgs,
)
from app.features.payments.service import Method, PaymentService

PROMPTS = load_prompts(prompts_py=__file__)


@dataclass(frozen=True)
class Write:
    """One change to the bank as a tool; `{fields}` in the path are arguments."""

    name: str
    title: str
    icon: str
    method: Method
    path: str
    args: type[BaseModel]
    # Required: the call reaches the bank only after the customer allows it in the page.
    confirmation: str


# A new write also goes into the service's WRITES, which is what may be changed.
WRITE_TOOLS = [
    Write(
        name="create_payment",
        title="Prepare a payment",
        icon="send",
        method="POST",
        path="/payments",
        args=PaymentCreateArgs,
        confirmation="Your bank receives this payment as pending and pays it on its date.",
    ),
    Write(
        name="update_payment",
        title="Change a pending payment",
        icon="pencil",
        method="PATCH",
        path="/payments/{payment_id}",
        args=PaymentUpdateArgs,
        confirmation="Your bank changes this pending payment.",
    ),
    Write(
        name="delete_payment",
        title="Delete a pending payment",
        icon="trash-2",
        method="DELETE",
        path="/payments/{payment_id}",
        args=PaymentArgs,
        confirmation="Your bank deletes this pending payment. It will not be paid.",
    ),
    Write(
        name="create_standing_order",
        title="Set up a standing order",
        icon="repeat",
        method="POST",
        path="/standing-orders",
        args=StandingOrderCreateArgs,
        confirmation="Your bank sets up this standing order and pays it on every due date.",
    ),
    Write(
        name="update_standing_order",
        title="Change a standing order",
        icon="pencil",
        method="PATCH",
        path="/standing-orders/{standing_order_id}",
        args=StandingOrderUpdateArgs,
        confirmation="Your bank changes this standing order for its next runs.",
    ),
    Write(
        name="delete_standing_order",
        title="Delete a standing order",
        icon="trash-2",
        method="DELETE",
        path="/standing-orders/{standing_order_id}",
        args=StandingOrderArgs,
        confirmation="Your bank deletes this standing order. It will not pay again.",
    ),
]


def get_tools(service: PaymentService, token: str) -> list[Tool[Any]]:
    return [_tool(write=write, service=service, token=token) for write in WRITE_TOOLS]


def _tool(write: Write, service: PaymentService, token: str) -> Tool[Any]:
    in_path = {field for _, field, _, _ in Formatter().parse(write.path) if field}

    async def handler(args: BaseModel) -> BankWrite:
        values = args.model_dump(mode="json", exclude_none=True)
        # Quoted, so an id the model made up cannot reach another path of the banking API.
        path = write.path.format(
            **{field: quote(str(values.pop(field)), safe="") for field in in_path}
        )
        body = None if write.method == "DELETE" else values
        return await service.write(method=write.method, path=path, token=token, body=body)

    return Tool(
        name=write.name,
        title=write.title,
        icon=write.icon,
        description=PROMPTS[write.name],
        args_schema=write.args,
        handler=handler,
        confirmation=write.confirmation,
        sheet=lambda args: service.sheet(args=args, token=token),
    )
