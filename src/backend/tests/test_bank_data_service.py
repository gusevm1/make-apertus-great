from app.features.bank_data.service import ROWS_MAX_CHARS, fit


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
