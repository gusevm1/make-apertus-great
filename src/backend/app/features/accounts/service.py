from decimal import Decimal

from app.features.accounts.schemas import AccountBalance, AccountBalances
from app.features.ledger.service import LedgerService


class AccountService:
    def __init__(self, ledger: LedgerService) -> None:
        self.ledger = ledger

    async def list_balances(self, token: str) -> AccountBalances:
        """The customer's accounts with their balances in CHF, and the sum, added up here."""
        data = await self.ledger.read(path="/accounts", token=token)
        accounts = [
            AccountBalance(
                account_id=item["account_id"],
                name=item["name"],
                type=item["type"],
                iban=item["iban"],
                # str first: the API sends floats, and Decimal(9716.33) is not 9716.33
                balance_chf=Decimal(str(item["current_balance_chf"])),
            )
            for item in data["items"]
        ]
        return AccountBalances(
            accounts=accounts,
            total_balance_chf=sum((account.balance_chf for account in accounts), Decimal(0)),
        )
