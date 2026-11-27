from app.features.figure_corrections.service import SOURCES_MAX_CHARS, last_sources

RESULT = '{"total_chf": 2916.35}'


def test_a_large_document_drops_out_before_the_tool_results() -> None:
    document = "x" * SOURCES_MAX_CHARS

    kept = last_sources(sources=[document, "Visa in October?", RESULT], max_chars=SOURCES_MAX_CHARS)

    assert kept == ["Visa in October?", RESULT]


def test_a_source_is_kept_whole_or_not_at_all() -> None:
    kept = last_sources(sources=["older result", RESULT], max_chars=len(RESULT) + 3)

    assert kept == [RESULT]
