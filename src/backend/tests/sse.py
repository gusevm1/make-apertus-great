import json
from typing import Any

import httpx2


def sse_events(response: httpx2.Response) -> list[tuple[str, dict[str, Any]]]:
    blocks = [block.split("\n") for block in response.text.strip().split("\n\n")]
    return [(lines[0].removeprefix("event: "), json.loads(lines[1][6:])) for lines in blocks]
