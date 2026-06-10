import os
from typing import Literal, cast

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

McpTransport = Literal["stdio", "sse", "streamable-http"]


def split_csv_env(name: str, default: str) -> list[str]:
    return [
        value.strip()
        for value in os.getenv(name, default).split(",")
        if value.strip()
    ]


def get_mcp_transport() -> McpTransport:
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport not in ("stdio", "sse", "streamable-http"):
        raise ValueError(
            "MCP_TRANSPORT must be one of: stdio, sse, streamable-http"
        )

    return cast(McpTransport, transport)


MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
MCP_SSE_PATH = os.getenv("MCP_SSE_PATH", "/sse")
MCP_MESSAGE_PATH = os.getenv("MCP_MESSAGE_PATH", "/messages/")
MCP_STREAMABLE_HTTP_PATH = os.getenv("MCP_STREAMABLE_HTTP_PATH", "/mcp")
MCP_TRANSPORT = get_mcp_transport()
MCP_ALLOWED_HOSTS = split_csv_env(
    "MCP_ALLOWED_HOSTS",
    "localhost:*,127.0.0.1:*,10.0.0.37:*",
)
MCP_ALLOWED_ORIGINS = split_csv_env(
    "MCP_ALLOWED_ORIGINS",
    "http://localhost:*,http://127.0.0.1:*,http://10.0.0.37:*",
)

mcp = FastMCP(
    "WeatherUnderground",
    host=MCP_HOST,
    port=MCP_PORT,
    sse_path=MCP_SSE_PATH,
    message_path=MCP_MESSAGE_PATH,
    streamable_http_path=MCP_STREAMABLE_HTTP_PATH,
    transport_security=TransportSecuritySettings(
        allowed_hosts=MCP_ALLOWED_HOSTS,
        allowed_origins=MCP_ALLOWED_ORIGINS,
    ),
)

API_KEY = os.getenv("WU_API_KEY")
STATION_ID = os.getenv("WU_STATION_ID", "KCAHUNTI63")
CURRENT_CONDITIONS_URL = "https://api.weather.com/v2/pws/observations/current"
DAILY_FORECAST_URL = "https://api.weather.com/v3/wx/forecast/daily/5day"


async def fetch_weather_json(
    url: str,
    params: dict[str, object],
) -> dict | str:
    if not API_KEY:
        return "Missing Weather Underground API key. Set WU_API_KEY."

    request_params = {**params, "apiKey": API_KEY}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=request_params)

    if response.status_code != 200:
        return f"Error fetching weather data: {response.text}"

    return response.json()


def format_daypart(daypart: dict, index: int) -> str | None:
    name = daypart["daypartName"][index]
    phrase = daypart["wxPhraseLong"][index]

    if not name or not phrase:
        return None

    precip_chance = daypart["precipChance"][index]
    wind_phrase = daypart["windPhrase"][index]
    summary = f"{name}: {phrase}"

    if precip_chance is not None:
        summary += f", precip {precip_chance}%"

    if wind_phrase:
        summary += f", {wind_phrase}"

    return summary


def format_temperature(value: int | None) -> str:
    if value is None:
        return "unavailable"

    return f"{value}°F"


async def get_current_conditions_payload() -> dict | str:
    data = await fetch_weather_json(
        CURRENT_CONDITIONS_URL,
        {
            "stationId": STATION_ID,
            "format": "json",
            "units": "e",
        },
    )

    if isinstance(data, str):
        return data

    observation = data["observations"][0]
    obs = observation["imperial"]

    return {
        "station_id": STATION_ID,
        "neighborhood": observation["neighborhood"],
        "observed_local": observation["obsTimeLocal"],
        "temperature_f": obs["temp"],
        "feels_like_f": obs["heatIndex"],
        "wind_chill_f": obs["windChill"],
        "dew_point_f": obs["dewpt"],
        "humidity_percent": observation["humidity"],
        "wind_speed_mph": obs["windSpeed"],
        "wind_direction_degrees": observation["winddir"],
        "wind_gust_mph": obs["windGust"],
        "pressure_inhg": obs["pressure"],
        "precip_rate_in_per_hr": obs["precipRate"],
        "precip_total_in": obs["precipTotal"],
        "solar_radiation": observation["solarRadiation"],
        "uv": observation["uv"],
        "elevation_ft": obs["elev"],
        "qc_status": observation["qcStatus"],
    }


async def get_forecast_payload() -> dict | str:
    current_data = await fetch_weather_json(
        CURRENT_CONDITIONS_URL,
        {
            "stationId": STATION_ID,
            "format": "json",
            "units": "e",
        },
    )

    if isinstance(current_data, str):
        return current_data

    observation = current_data["observations"][0]
    geocode = f"{observation['lat']},{observation['lon']}"
    forecast_data = await fetch_weather_json(
        DAILY_FORECAST_URL,
        {
            "geocode": geocode,
            "format": "json",
            "units": "e",
            "language": "en-US",
        },
    )

    if isinstance(forecast_data, str):
        return forecast_data

    daypart = forecast_data["daypart"][0]
    forecast_days = min(5, len(forecast_data["dayOfWeek"]))
    days = []

    for day_index in range(forecast_days):
        days.append(
            {
                "day": forecast_data["dayOfWeek"][day_index],
                "high_f": forecast_data["temperatureMax"][day_index],
                "low_f": forecast_data["temperatureMin"][day_index],
                "narrative": forecast_data["narrative"][day_index],
                "day_summary": format_daypart(daypart, day_index * 2),
                "night_summary": format_daypart(daypart, day_index * 2 + 1),
            }
        )

    return {
        "station_id": STATION_ID,
        "neighborhood": observation["neighborhood"],
        "days": days,
    }


@mcp.tool()
async def get_current_conditions() -> str:
    """Get current weather for your configured Weather Underground station."""
    conditions = await get_current_conditions_payload()

    if isinstance(conditions, str):
        return conditions

    return (
        f"Current weather in {conditions['neighborhood']} "
        f"(Station ID: {STATION_ID})\n"
        f"Observed local: {conditions['observed_local']}\n"
        f"Temperature: {conditions['temperature_f']}°F\n"
        f"Feels like: {conditions['feels_like_f']}°F\n"
        f"Wind chill: {conditions['wind_chill_f']}°F\n"
        f"Dew point: {conditions['dew_point_f']}°F\n"
        f"Humidity: {conditions['humidity_percent']}%\n"
        f"Wind: {conditions['wind_speed_mph']} mph from "
        f"{conditions['wind_direction_degrees']}°\n"
        f"Wind gust: {conditions['wind_gust_mph']} mph\n"
        f"Pressure: {conditions['pressure_inhg']} inHg\n"
        f"Precip rate: {conditions['precip_rate_in_per_hr']} in/hr\n"
        f"Precip total: {conditions['precip_total_in']} in\n"
        f"Solar radiation: {conditions['solar_radiation']}\n"
        f"UV: {conditions['uv']}\n"
        f"Elevation: {conditions['elevation_ft']} ft\n"
        f"QC status: {conditions['qc_status']}"
    )


@mcp.tool()
async def get_forecast() -> str:
    """Get a 5-day forecast for your configured Weather Underground station."""
    forecast = await get_forecast_payload()

    if isinstance(forecast, str):
        return forecast

    lines = [
        f"5-day forecast for {forecast['neighborhood']} "
        f"(Station ID: {STATION_ID})"
    ]

    for day in forecast["days"]:
        lines.append(
            f"\n{day['day']}: High {format_temperature(day['high_f'])} / "
            f"Low {format_temperature(day['low_f'])}\n"
            f"Summary: {day['narrative']}"
        )

        if day["day_summary"]:
            lines.append(day["day_summary"])

        if day["night_summary"]:
            lines.append(day["night_summary"])

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport=MCP_TRANSPORT)
