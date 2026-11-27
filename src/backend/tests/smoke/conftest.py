from collections.abc import Iterator

import pytest

from app.features.tool_calls.dependencies import get_tools
from app.main import app
from tests.lookup_tool import LOOKUP


@pytest.fixture
def lookup_tool() -> Iterator[None]:
    """Offers `LOOKUP` as the app's only tool."""
    app.dependency_overrides[get_tools] = lambda: [LOOKUP]
    yield
    del app.dependency_overrides[get_tools]
