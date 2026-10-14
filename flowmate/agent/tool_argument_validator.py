from typing import Any, Mapping

from pydantic import BaseModel, ValidationError

from flowmate.tools.registry import ToolNotFoundError, ToolRegistry


class ToolArgumentValidationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        tool_name: str | None = None,
        arguments: Mapping[str, Any] | None = None,
        predicted_tools: list[str] | None = None,
        predicted_arguments: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.arguments = dict(arguments or {})
        self.predicted_tools = predicted_tools or ([] if tool_name is None else [tool_name])
        self.predicted_arguments = predicted_arguments or (
            {} if tool_name is None else {tool_name: dict(arguments or {})}
        )


class ToolArgumentValidator:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def validate(self, tool_name: str, arguments: Mapping[str, Any]) -> BaseModel:
        try:
            tool = self.registry.get(tool_name)
        except ToolNotFoundError as exc:
            raise ToolArgumentValidationError(
                f"Tool not found for argument validation: {tool_name}",
                tool_name=tool_name,
                arguments=arguments,
            ) from exc

        try:
            return tool.input_schema.model_validate(dict(arguments))
        except ValidationError as exc:
            raise ToolArgumentValidationError(
                f"Invalid arguments for {tool_name}: {exc}",
                tool_name=tool_name,
                arguments=arguments,
            ) from exc


def build_planner_tool_spec(registry: ToolRegistry, allowed_tools: set[str]) -> str:
    lines: list[str] = []
    for tool_info in registry.list_tools():
        if tool_info.name not in allowed_tools:
            continue

        tool = registry.get(tool_info.name)
        required_arguments = [
            field_name
            for field_name, field_info in tool.input_schema.model_fields.items()
            if field_info.is_required()
        ]
        optional_arguments = [
            field_name
            for field_name, field_info in tool.input_schema.model_fields.items()
            if not field_info.is_required()
        ]

        lines.extend(
            [
                f"{tool.name}",
                f"Purpose: {tool.description}",
                "Required arguments:",
                *[f"- {argument}" for argument in required_arguments],
            ]
        )
        if optional_arguments:
            lines.extend(
                [
                    "Optional arguments:",
                    *[f"- {argument}" for argument in optional_arguments],
                ]
            )
        lines.append("")

    return "\n".join(lines).strip()
