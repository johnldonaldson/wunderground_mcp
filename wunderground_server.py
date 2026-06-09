import os
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("WeatherUnderground")

# Load your Weather Underground credentials
API_KEY = os.getenv("WU_API_KEY")
STATION_ID = os.getenv("WU_STATION_ID", "KCAHUNTI63")  # Replace with your PWS
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


@mcp.tool()
async def get_current_conditions() -> str:
    """Get current weather for your configured Weather Underground station."""
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

    # Parse the observation data
    observation = data["observations"][0]
    obs = observation["imperial"]

    return (
        f"Current weather in {observation['neighborhood']} "
        f"(Station ID: {STATION_ID})\n"
        f"Observed local: {observation['obsTimeLocal']}\n"
        f"Temperature: {obs['temp']}°F\n"
        f"Feels like: {obs['heatIndex']}°F\n"
        f"Wind chill: {obs['windChill']}°F\n"
        f"Dew point: {obs['dewpt']}°F\n"
        f"Humidity: {observation['humidity']}%\n"
        f"Wind: {obs['windSpeed']} mph from {observation['winddir']}°\n"
        f"Wind gust: {obs['windGust']} mph\n"
        f"Pressure: {obs['pressure']} inHg\n"
        f"Precip rate: {obs['precipRate']} in/hr\n"
        f"Precip total: {obs['precipTotal']} in\n"
        f"Solar radiation: {observation['solarRadiation']}\n"
        f"UV: {observation['uv']}\n"
        f"Elevation: {obs['elev']} ft\n"
        f"QC status: {observation['qcStatus']}"
    )


@mcp.tool()
async def get_forecast() -> str:
    """Get a 5-day forecast for your configured Weather Underground station."""
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
    lines = [
        f"5-day forecast for {observation['neighborhood']} "
        f"(Station ID: {STATION_ID})"
    ]

    forecast_days = min(5, len(forecast_data["dayOfWeek"]))

    for day_index in range(forecast_days):
        day_name = forecast_data["dayOfWeek"][day_index]
        high = forecast_data["temperatureMax"][day_index]
        low = forecast_data["temperatureMin"][day_index]
        narrative = forecast_data["narrative"][day_index]
        day_summary = format_daypart(daypart, day_index * 2)
        night_summary = format_daypart(daypart, day_index * 2 + 1)

        lines.append(
            f"\n{day_name}: High {format_temperature(high)} / "
            f"Low {format_temperature(low)}\n"
            f"Summary: {narrative}"
        )

        if day_summary:
            lines.append(day_summary)

        if night_summary:
            lines.append(night_summary)

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
