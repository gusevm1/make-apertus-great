import re
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

PATH_PATTERN = r"^[A-Za-z_]\w*(\[\d+\])?(\.[A-Za-z_]\w*(\[\d+\])?)*$"
FIELD_PATTERN = r"^[A-Za-z_]\w*$"
# A path into DATA such as "months[5].total_chf"; a figure itself is never accepted.
DataPath = Annotated[str, Field(strict=True, max_length=120, pattern=PATH_PATTERN)]
# The name of a field of the rows a path points to, such as "total_chf".
FieldName = Annotated[str, Field(strict=True, max_length=60, pattern=FIELD_PATTERN)]
Label = Annotated[str, Field(strict=True, min_length=1, max_length=80)]


class Component(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Kpi(Component):
    type: Literal["kpi"]
    label: Label
    value: DataPath
    compare: DataPath | None = None
    compare_label: Label | None = None


class Stat(Component):
    label: Label
    value: DataPath


class StatRow(Component):
    type: Literal["stat_row"]
    stats: list[Stat] = Field(min_length=2, max_length=4)


class Table(Component):
    type: Literal["table"]
    title: Label | None = None
    rows: DataPath
    columns: list[FieldName] = Field(min_length=1, max_length=5)
    total: DataPath | None = None

    @model_validator(mode="after")
    def _total_has_a_column(self) -> Self:
        if self.total is not None and self.total_column() is None:
            raise ValueError("a total needs a column for it: name a column ending in _chf")
        return self

    def total_column(self) -> str | None:
        """The column the total sits under: the one named like its field, else the first amount."""
        if self.total is None:
            return None
        field = re.findall(r"[A-Za-z_]\w*", self.total)[-1]
        if field in self.columns:
            return field
        return next((column for column in self.columns if column.endswith("_chf")), None)


class ItemList(Component):
    type: Literal["list"]
    title: Label | None = None
    rows: DataPath
    label: FieldName
    value: FieldName
    detail: FieldName | None = None


class BarChart(Component):
    type: Literal["bar_chart"]
    title: Label | None = None
    data: DataPath
    x: FieldName
    y: FieldName
    # A value of `x` to draw in the accent colour, such as "2026-10".
    highlight: Label | None = None
    horizontal: bool = False


class LineChart(Component):
    type: Literal["line_chart"]
    title: Label | None = None
    data: DataPath
    x: FieldName
    y: FieldName
    series: FieldName | None = None


class Stack(Component):
    type: Literal["stack"]
    children: list["Node"] = Field(min_length=1, max_length=8)


class Grid(Component):
    type: Literal["grid"]
    columns: Literal[2, 3] = 2
    children: list["Node"] = Field(min_length=2, max_length=6)


Node = Annotated[
    Kpi | StatRow | Table | ItemList | BarChart | LineChart | Stack | Grid,
    Field(discriminator="type"),
]
Stack.model_rebuild()
Grid.model_rebuild()

COMPONENTS: list[type[Component]] = [
    Kpi,
    StatRow,
    Table,
    ItemList,
    BarChart,
    LineChart,
    Stack,
    Grid,
]


class WidgetSpec(Component):
    title: Label
    subtitle: Label | None = None
    body: Node
