from typing import Any

from app.features.bank_data.schemas import BankData
from app.features.bank_data.service import ROWS_MAX_CHARS, BankDataService, fit
from app.features.bank_data.tools import get_tools


def test_empty_fields_are_dropped_and_sums_kept() -> None:
    data = {"items": [{"booking_id": "BK-1", "reference": None}], "sum_debit": -12.5, "note": None}

    assert fit(data=data) == {"items": [{"booking_id": "BK-1"}], "sum_debit": -12.5}


def test_rows_beyond_the_room_are_counted_not_listed() -> None:
    row = {"booking_text": "x" * 1000}
    data = {"items": [row] * 10, "total": 10, "sum_debit": -99.0}

    fitted = fit(data=data)

    assert len(fitted["items"]) == ROWS_MAX_CHARS // 1000 - 1
    assert fitted["items_not_listed"] == 10 - len(fitted["items"])
    assert (fitted["total"], fitted["sum_debit"]) == (10, -99.0)


class _Recorder(BankDataService):
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.params: dict[str, Any] = {}

    async def read(self, path: str, token: str, params: dict[str, Any]) -> BankData:
        self.paths.append(path)
        self.params = params
        return BankData(root={})


async def test_an_id_cannot_reach_another_path_of_the_banking_api() -> None:
    recorder = _Recorder()
    tools = {tool.name: tool for tool in get_tools(service=recorder, token="token")}
    preview = tools["get_balance_preview"]
    assert preview.handler is not None

    await preview.handler(preview.args_schema(account_id="../customer?x="))

    assert recorder.paths == ["/accounts/..%2Fcustomer%3Fx%3D/balance-preview"]


async def test_asking_for_chf_rates_asks_for_all_rates_against_chf() -> None:
    recorder = _Recorder()
    tools = {tool.name: tool for tool in get_tools(service=recorder, token="token")}
    rates = tools["get_fx_rates"]
    assert rates.handler is not None

    await rates.handler(rates.args_schema.model_validate({"currency": "CHF", "month": "2025-06"}))

    assert recorder.params == {"month": "2025-06"}
