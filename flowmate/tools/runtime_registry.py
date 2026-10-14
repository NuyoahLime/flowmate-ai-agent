from __future__ import annotations

import os
from enum import Enum

from flowmate.tools.navigation import NavigationTool
from flowmate.tools.registry import ToolRegistry, create_default_registry
from flowmate.tools.weather import WeatherTool


TOOL_MODE_ENV = "FLOWMATE_TOOL_MODE"


class RuntimeToolConfigurationError(ValueError):
    pass


class RuntimeToolMode(str, Enum):
    MOCK = "mock"
    REAL_INFORMATION = "real_information"


def runtime_tool_mode_from_env() -> RuntimeToolMode:
    raw_mode = os.getenv(TOOL_MODE_ENV, RuntimeToolMode.MOCK.value)
    try:
        return RuntimeToolMode(raw_mode.strip().lower())
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in RuntimeToolMode)
        raise RuntimeToolConfigurationError(
            f"{TOOL_MODE_ENV} must be one of: {allowed}."
        ) from exc


def create_runtime_registry_from_env() -> ToolRegistry:
    mode = runtime_tool_mode_from_env()
    if mode == RuntimeToolMode.MOCK:
        return create_default_registry()

    weather_tool, navigation_tool = _create_real_information_tools()
    return create_default_registry(
        weather_tool=weather_tool,
        navigation_tool=navigation_tool,
    )


def _create_real_information_tools() -> tuple[WeatherTool, NavigationTool]:
    # Keep provider adapters lazy so importing either integration package does not
    # re-enter flowmate.tools through its result models.
    from flowmate.integrations.navigation import (
        AmapNavigationProvider,
        NavigationConfigurationError,
    )
    from flowmate.integrations.weather import (
        OpenMeteoWeatherProvider,
        WeatherConfigurationError,
    )

    try:
        weather_provider = OpenMeteoWeatherProvider()
        navigation_provider = AmapNavigationProvider()
    except (WeatherConfigurationError, NavigationConfigurationError) as exc:
        raise RuntimeToolConfigurationError(str(exc)) from exc

    return (
        WeatherTool(provider=weather_provider),
        NavigationTool(provider=navigation_provider),
    )


def runtime_provider_status() -> dict[str, str]:
    mode = runtime_tool_mode_from_env()
    if mode == RuntimeToolMode.REAL_INFORMATION:
        # Validate the same adapter configuration used by the Agent runtime
        # before reporting the providers as active.
        _create_real_information_tools()
        information_providers = {
            "weather": "Open-Meteo Real Active",
            "navigation": "Amap Real Active",
        }
    else:
        information_providers = {
            "weather": "Mock",
            "navigation": "Mock",
        }
    return {
        "calendar": "Mock",
        **information_providers,
        "notification": "Mock",
        "smart_home": "Mock",
        "vehicle": "Mock",
    }
