from typing import Any

from pydantic import BaseModel, Field

from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.web_search.schemas import WebSearch
from app.features.web_search.service import WebSearchService

PROMPTS = load_prompts(prompts_py=__file__)


class SearchWebArgs(BaseModel):
    query: str = Field(min_length=1, description=PROMPTS["search_web_query"])


def get_tools(service: WebSearchService) -> list[Tool[Any]]:
    async def search_web(args: SearchWebArgs) -> WebSearch:
        return await service.search_web(query=args.query)

    return [
        Tool(
            name="search_web",
            title="Search the web",
            icon="globe",
            description=PROMPTS["search_web"],
            args_schema=SearchWebArgs,
            handler=search_web,
            confirmation="This sends the query to search engines outside the bank.",
            is_editable=True,
        )
    ]
