"""OpenWeather API integration — fetch weather once per route request.

Returns WeatherCondition enum value used for D(w) scoring.
"""

from __future__ import annotations

import httpx

from config import settings
from constants import WeatherCondition

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_TIMEOUT = 5.0

# OpenWeather 'main' field → WeatherCondition mapping
_CONDITION_MAP: dict[str, WeatherCondition] = {
    "Clear": WeatherCondition.CLEAR,
    "Clouds": WeatherCondition.CLOUDY,
    "Rain": WeatherCondition.RAIN,
    "Drizzle": WeatherCondition.RAIN,
    "Thunderstorm": WeatherCondition.RAIN,
    "Snow": WeatherCondition.SNOW,
    "Mist": WeatherCondition.FOG,
    "Fog": WeatherCondition.FOG,
    "Haze": WeatherCondition.FOG,
    "Smoke": WeatherCondition.FOG,
}


async def fetch_weather(lat: float, lon: float) -> str:
    """Fetch current weather condition at a location.

    Args:
        lat: Latitude (WGS84)
        lon: Longitude (WGS84)

    Returns:
        WeatherCondition enum value (e.g. "CLEAR", "RAIN").
        Falls back to "CLEAR" on API failure or missing key.
    """
    if not settings.openweather_api_key:
        return WeatherCondition.CLEAR.value

    params = {
        "lat": str(lat),
        "lon": str(lon),
        "appid": settings.openweather_api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=OPENWEATHER_TIMEOUT) as client:
            resp = await client.get(OPENWEATHER_URL, params=params)
    except (httpx.TimeoutException, httpx.RequestError):
        return WeatherCondition.CLEAR.value

    if resp.status_code != 200:
        return WeatherCondition.CLEAR.value

    data = resp.json()
    weather_list = data.get("weather", [])
    if not weather_list:
        return WeatherCondition.CLEAR.value

    main_condition = weather_list[0].get("main", "Clear")
    condition = _CONDITION_MAP.get(main_condition, WeatherCondition.CLEAR)
    return condition.value
