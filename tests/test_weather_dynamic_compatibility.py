from flowmate.agent import DynamicTaskOrchestrator, ToolExecutor
from flowmate.integrations.weather import WeatherProviderQuery
from flowmate.schemas import DynamicPlanningPhase
from flowmate.tools import CalendarTool, NavigationTool, ToolRegistry, WeatherTool
from flowmate.tools.weather import WeatherToolResult


class RealShapedWeatherProvider:
    def get_weather(self, query: WeatherProviderQuery) -> WeatherToolResult:
        return WeatherToolResult(
            location="Shanghai",
            date=query.date,
            condition="cloudy",
            temperature_c=22.0,
            rain_probability=0.2,
        )


def test_dynamic_weather_continuation_accepts_real_shaped_provider_result():
    registry = ToolRegistry()
    registry.register(WeatherTool(provider=RealShapedWeatherProvider()))
    registry.register(NavigationTool())
    registry.register(CalendarTool())
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(registry))

    state = orchestrator.execute(
        "help me plan tomorrow morning departure and check weather"
    )

    assert state.phase == DynamicPlanningPhase.COMPLETED
    assert state.final_result.weather_result == {
        "location": "Shanghai",
        "date": "tomorrow",
        "condition": "cloudy",
        "temperature_c": 22.0,
        "rain_probability": 0.2,
    }
