from typing import TypedDict


class StatValue(TypedDict):
    name: str
    value: int | str | list[str]


class ParsedStats(TypedDict):
    character: dict[str, int | str | list[str]]
    world: dict[str, int | str | list[str]]


class ToolCallRecord(TypedDict):
    tool_name: str
    arguments: dict[str, str]
    result: str
