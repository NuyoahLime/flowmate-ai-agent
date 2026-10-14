from flowmate.integrations.weather.provider import WeatherProviderQuery
from flowmate.tools.weather import WeatherToolResult


class MockWeatherProvider:
    def get_weather(self, query: WeatherProviderQuery) -> WeatherToolResult:
        return WeatherToolResult(
            location=query.location,
            date=query.date,
            condition="rain",
            temperature_c=18,
            rain_probability=0.8,
        )
