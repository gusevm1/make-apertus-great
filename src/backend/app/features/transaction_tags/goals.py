from app.features.ledger.service import LedgerService

MAX_GOAL_TEXTS = 20


async def read_goal_hints(ledger: LedgerService, token: str) -> tuple[list[str], list[str]]:
    """The customer's account names and own-account standing orders: what they may save for."""
    accounts = await ledger.read(path="/accounts", token=token)
    orders = await ledger.read(path="/standing-orders", token=token)
    transfers = [
        f"{order['payee_name']}: {order['message']}, CHF {order['amount']} {order['frequency']}"
        for order in orders["items"]
        if order.get("credit_account_id") is not None
    ]
    account_names = [account["name"] for account in accounts["items"]]
    return account_names[:MAX_GOAL_TEXTS], transfers[:MAX_GOAL_TEXTS]
