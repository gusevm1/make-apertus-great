"""Which upcoming payments are subscriptions, from the bank's own payment text."""

import re
from typing import Any

# ponytail: keywords in German bank texts, so a subscription the text does not name is missed;
# a category per payee once the categorisation feature covers payees
SUBSCRIPTION = re.compile(
    r"\babo\b|abonnement|mitgliedschaft|membership|\bmobile\b|internet|inone|\btv\b|streaming"
    r"|netflix|spotify|disney|youtube|icloud|microsoft",
    re.IGNORECASE,
)
NOT_SUBSCRIPTION = re.compile(
    r"miete|prämie|praemie|steuer|\brate\b|ratenvertrag|leasing|zins|spende|sparplan|rücklage"
    r"|sparen|säule|einzahlung|abrechnung",
    re.IGNORECASE,
)
OWN_ACCOUNT_TYPES = {"account_transfer", "card_statement"}
PAYEES_MAX = 8


def subscription_payees(payments: list[dict[str, Any]]) -> list[str]:
    """The payees of every subscription among `payments`, by the bank's own payment text."""
    return list(
        dict.fromkeys(
            payment["payee_name"]
            for payment in payments
            if payment["type"] not in OWN_ACCOUNT_TYPES
            and SUBSCRIPTION.search(payment["description"]) is not None
            and NOT_SUBSCRIPTION.search(payment["description"]) is None
        )
    )[:PAYEES_MAX]
