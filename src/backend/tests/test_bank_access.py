import ast
from pathlib import Path

import pytest

from app.core.errors import BadRequestError
from app.features.bank_data.service import BankDataService
from app.features.bank_data.tools import READS, get_tools
from app.features.ledger.service import READ_PATHS, LedgerService

FEATURES = Path(__file__).parents[1] / "app" / "features"
# The ledger reads for the model's tools; documents only stores an upload in the bank.
MAY_CALL_THE_BANK = {"ledger", "documents"}


def _imports_banking(source: Path) -> bool:
    tree = ast.parse(source.read_text())
    return any(
        isinstance(node, ast.ImportFrom) and node.module == "app.clients.banking"
        for node in ast.walk(tree)
    )


def test_only_the_ledger_reads_the_bank_for_the_model() -> None:
    callers = {
        source.relative_to(FEATURES).parts[0]
        for source in FEATURES.rglob("*.py")
        if _imports_banking(source=source)
    }

    assert callers <= MAY_CALL_THE_BANK


def test_every_bank_data_tool_reads_a_path_the_ledger_allows() -> None:
    allowed = {path.replace("{}", "{x}") for path in READ_PATHS}

    for read in READS:
        fields = read.args.model_fields
        assert read.path.format(**{field: "{x}" for field in fields}) in allowed, read.name


class _Bank:
    def __init__(self) -> None:
        self.paths: list[str] = []

    async def get(self, path: str, token: str | None = None, params: object = None) -> dict:
        self.paths.append(path)
        return {}


async def test_an_id_of_dots_cannot_climb_to_another_path() -> None:
    bank = _Bank()
    service = BankDataService(ledger=LedgerService(banking=bank))  # type: ignore[arg-type]
    tools = {tool.name: tool for tool in get_tools(service=service, token="token")}
    preview = tools["get_balance_preview"]

    with pytest.raises(BadRequestError, match="is not a read the bank data allows"):
        await preview.handler(preview.args_schema(account_id=".."))

    assert bank.paths == []
