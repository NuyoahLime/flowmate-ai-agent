from typing import Any

from pydantic import BaseModel

from flowmate.tools.base import BaseTool
from flowmate.tools.calendar import CalendarTool
from flowmate.tools.navigation import NavigationTool
from flowmate.tools.notification import NotificationTool
from flowmate.tools.smart_home import SmartHomeTool
from flowmate.tools.vehicle import VehicleTool
from flowmate.tools.weather import WeatherTool


class ToolRegistryError(Exception):
    pass


class DuplicateToolError(ToolRegistryError, ValueError):
    pass


class ToolNotFoundError(ToolRegistryError, KeyError):
    pass


class ToolInfo(BaseModel):
    name: str
    description: str


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool[Any, Any]] = {}

    def register(self, tool: BaseTool[Any, Any]) -> None:
        if tool.name in self._tools:
            raise DuplicateToolError(f"Tool already registered: {tool.name}")

        self._tools[tool.name] = tool

    def get(self, tool_name: str) -> BaseTool[Any, Any]:
        try:
            return self._tools[tool_name]
        except KeyError as exc:
            raise ToolNotFoundError(f"Tool not found: {tool_name}") from exc

    def list_tools(self) -> list[ToolInfo]:
        return [
            ToolInfo(name=tool.name, description=tool.description)
            for tool in self._tools.values()
        ]


def create_default_registry(
    calendar_tool: CalendarTool | None = None,
    weather_tool: WeatherTool | None = None,
    navigation_tool: NavigationTool | None = None,
    notification_tool: NotificationTool | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(weather_tool or WeatherTool())
    registry.register(navigation_tool or NavigationTool())
    registry.register(calendar_tool or CalendarTool())
    registry.register(notification_tool or NotificationTool())
    registry.register(SmartHomeTool())
    registry.register(VehicleTool())
    return registry
