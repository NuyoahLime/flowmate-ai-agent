import pytest

from flowmate.tools import (
    CalendarTool,
    DuplicateToolError,
    NavigationTool,
    NotificationTool,
    SmartHomeTool,
    ToolNotFoundError,
    ToolRegistry,
    VehicleTool,
    WeatherTool,
    create_default_registry,
)


def test_can_register_weather_tool():
    registry = ToolRegistry()
    weather_tool = WeatherTool()

    registry.register(weather_tool)

    assert registry.get("weather_tool") is weather_tool


def test_can_register_navigation_tool():
    registry = ToolRegistry()
    navigation_tool = NavigationTool()

    registry.register(navigation_tool)

    assert registry.get("navigation_tool") is navigation_tool


def test_can_get_tool_by_name():
    registry = ToolRegistry()
    weather_tool = WeatherTool()
    registry.register(weather_tool)

    tool = registry.get("weather_tool")

    assert isinstance(tool, WeatherTool)


def test_list_tools_returns_registered_tool_info():
    registry = ToolRegistry()
    registry.register(WeatherTool())
    registry.register(NavigationTool())
    registry.register(CalendarTool())
    registry.register(NotificationTool())
    registry.register(SmartHomeTool())
    registry.register(VehicleTool())

    tools = registry.list_tools()

    assert [tool.name for tool in tools] == [
        "weather_tool",
        "navigation_tool",
        "calendar_tool",
        "notification_tool",
        "smart_home_tool",
        "vehicle_tool",
    ]
    assert all(tool.description for tool in tools)


def test_duplicate_tool_name_registration_fails():
    registry = ToolRegistry()
    registry.register(WeatherTool())

    with pytest.raises(DuplicateToolError):
        registry.register(WeatherTool())


def test_get_unknown_tool_fails():
    registry = ToolRegistry()

    with pytest.raises(ToolNotFoundError):
        registry.get("missing_tool")


def test_create_default_registry_contains_available_tools():
    registry = create_default_registry()

    tool_names = [tool.name for tool in registry.list_tools()]

    assert tool_names == [
        "weather_tool",
        "navigation_tool",
        "calendar_tool",
        "notification_tool",
        "smart_home_tool",
        "vehicle_tool",
    ]
    assert isinstance(registry.get("weather_tool"), WeatherTool)
    assert isinstance(registry.get("navigation_tool"), NavigationTool)
    assert isinstance(registry.get("calendar_tool"), CalendarTool)
    assert isinstance(registry.get("notification_tool"), NotificationTool)
    assert isinstance(registry.get("smart_home_tool"), SmartHomeTool)
    assert isinstance(registry.get("vehicle_tool"), VehicleTool)
