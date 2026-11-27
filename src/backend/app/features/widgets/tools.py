from typing import Any
from uuid import UUID

from app.core.tools import Tool, Turn
from app.features.widgets.schemas import PROMPTS, BuildWidgetArgs, BuiltWidget
from app.features.widgets.service import BUILD_WIDGET, WidgetService


def get_tools(service: WidgetService, owner_id: UUID) -> list[Tool[Any]]:
    async def build_widget(args: BuildWidgetArgs, turn: Turn) -> BuiltWidget:
        return await service.build_widget(
            owner_id=owner_id,
            conversation_id=turn.conversation_id,
            args=args,
            results=turn.results,
        )

    return [
        Tool(
            name=BUILD_WIDGET,
            title="Draw a widget",
            icon="layout-dashboard",
            description=PROMPTS[BUILD_WIDGET],
            args_schema=BuildWidgetArgs,
            turn_handler=build_widget,
        )
    ]
