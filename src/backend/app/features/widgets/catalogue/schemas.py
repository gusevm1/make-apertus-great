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
Note = Annotated[str, Field(strict=True, min_length=1, max_length=200)]
# The palette a customer chooses chart colours from; charts.PALETTE holds their values.
ColourName = Literal[
    "petrol",
    "petrol_light",
    "navy",
    "navy_light",
    "grey",
    "grey_light",
    "red",
    "red_light",
    "green",
    "green_light",
    "blue",
    "blue_light",
    "amber",
    "amber_light",
]
# A row label or series value of the chart's data, such as "2026-10" or "2025", to a colour.
Colours = Annotated[dict[Label, ColourName], Field(max_length=24)]


class Component(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Trend(Component):
    data: DataPath
    x: FieldName
    y: FieldName


class Stat(Component):
    label: Label
    value: DataPath
    # A small line of the series the figure belongs to, such as the last months.
    trend: Trend | None = None
    # A change figure DATA holds; `good_when` says which way is good (down for spending).
    change: DataPath | None = None
    good_when: Literal["up", "down"] | None = None

    @model_validator(mode="after")
    def _change_says_which_way_is_good(self) -> Self:
        if self.change is not None and self.good_when is None:
            raise ValueError("a change needs good_when: up or down")
        return self


class Kpi(Stat):
    type: Literal["kpi"]
    compare: DataPath | None = None
    compare_label: Label | None = None


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
    highlight_color: ColourName | None = None
    horizontal: bool = False
    colors: Colours | None = None

    @model_validator(mode="after")
    def _highlight_color_needs_a_highlight(self) -> Self:
        if self.highlight_color is not None and self.highlight is None:
            raise ValueError("highlight_color needs highlight: the label to draw in it")
        return self


class LineChart(Component):
    type: Literal["line_chart"]
    title: Label | None = None
    data: DataPath
    x: FieldName
    y: FieldName
    series: FieldName | None = None
    colors: Colours | None = None


class AreaChart(Component):
    type: Literal["area_chart"]
    title: Label | None = None
    data: DataPath
    x: FieldName
    y: FieldName
    series: FieldName | None = None
    colors: Colours | None = None


class Comparison(Component):
    type: Literal["comparison"]
    title: Label | None = None
    data: DataPath
    x: FieldName
    y: FieldName
    series: FieldName
    colors: Colours | None = None


class Donut(Component):
    type: Literal["donut"]
    title: Label | None = None
    data: DataPath
    label: FieldName
    value: FieldName
    total: DataPath | None = None
    colors: Colours | None = None


class ForecastChart(Component):
    type: Literal["forecast_chart"]
    title: Label | None = None
    data: DataPath
    x: FieldName
    y: FieldName
    # The field that says "actual" or "forecast" for each row; actual rows come first.
    kind: FieldName
    # Fields of the forecast rows that hold the lower and upper end of their range.
    low: FieldName | None = None
    high: FieldName | None = None

    @model_validator(mode="after")
    def _range_has_both_ends(self) -> Self:
        if (self.low is None) != (self.high is None):
            raise ValueError("a range needs both low and high")
        return self


class ScenarioFigure(Component):
    label: Label
    # A field of every case's row, such as "left_chf".
    field: FieldName


class Scenarios(Component):
    type: Literal["scenarios"]
    title: Label | None = None
    # The cases, one row each, such as rent today, +200 and +400.
    data: DataPath
    # The field that names each case.
    label: FieldName
    figures: list[ScenarioFigure] = Field(min_length=1, max_length=4)


class Timeline(Component):
    type: Literal["timeline"]
    title: Label | None = None
    rows: DataPath
    date: FieldName
    label: FieldName
    value: FieldName
    detail: FieldName | None = None


class Progress(Component):
    type: Literal["progress"]
    label: Label
    value: DataPath
    goal: DataPath
    goal_label: Label | None = None


class Callout(Component):
    type: Literal["callout"]
    title: Label | None = None
    text: Note
    tone: Literal["info", "warning"] = "info"


class Stack(Component):
    type: Literal["stack"]
    children: list["Node"] = Field(min_length=1, max_length=8)


class Grid(Component):
    type: Literal["grid"]
    columns: Literal[2, 3] = 2
    children: list["Node"] = Field(min_length=2, max_length=6)


Chart = BarChart | LineChart | AreaChart | Comparison | Donut | ForecastChart
Node = Annotated[
    Kpi
    | StatRow
    | Table
    | ItemList
    | Timeline
    | BarChart
    | LineChart
    | AreaChart
    | Comparison
    | Donut
    | ForecastChart
    | Scenarios
    | Progress
    | Callout
    | Stack
    | Grid,
    Field(discriminator="type"),
]
Stack.model_rebuild()
Grid.model_rebuild()

COMPONENTS: list[type[Component]] = [
    Kpi,
    StatRow,
    Table,
    ItemList,
    Timeline,
    BarChart,
    LineChart,
    AreaChart,
    Comparison,
    Donut,
    ForecastChart,
    Scenarios,
    Progress,
    Callout,
    Stack,
    Grid,
]


class WidgetSpec(Component):
    title: Label
    subtitle: Label | None = None
    body: Node
