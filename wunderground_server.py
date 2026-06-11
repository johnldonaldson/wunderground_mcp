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
NEAREST_STATION_URL = (
    "https://api.weather.com/v2/pws/observations/nearest"
)
DAILY_FORECAST_URL = "https://api.weather.com/v3/wx/forecast/daily/5day"
LOCATION_SEARCH_URL = "https://api.weather.com/v3/location/search"


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
    name = get_indexed_weather_value(daypart, "daypartName", index)
    phrase = get_indexed_weather_value(daypart, "wxPhraseLong", index)

    if not name or not phrase:
        return None

    precip_chance = get_indexed_weather_value(daypart, "precipChance", index)
    wind_phrase = get_indexed_weather_value(daypart, "windPhrase", index)
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


def get_indexed_weather_value(
    weather_data: dict,
    key: str,
    index: int,
) -> object | None:
    values = weather_data.get(key)

    if not isinstance(values, list) or index >= len(values):
        return None

    return values[index]


def format_city_state_location(location: dict) -> str:
    city = location.get("city")
    state = location.get("state")

    if city and state:
        return f"{city}, {state}"

    return str(location.get("query", "requested location"))


def get_indexed_location_value(location_data: dict, key: str) -> object | None:
    values = location_data.get(key)

    if not isinstance(values, list) or not values:
        return None

    return values[0]


def normalize_city_state_input(city: str, state: str) -> tuple[str, str]:
    city = city.strip()
    state = state.strip()

    if not state and "," in city:
        city, state = [part.strip() for part in city.split(",", 1)]

    if not state:
        city_parts = city.rsplit(maxsplit=1)

        if len(city_parts) == 2 and len(city_parts[1]) == 2:
            city, state = city_parts

    if len(state) == 2:
        state = state.upper()

    return city, state


async def resolve_city_state_location(city: str, state: str) -> dict | str:
    city, state = normalize_city_state_input(city, state)

    if not city or not state:
        return (
            "Specify both city and state, for example "
            "city='Huntington Beach', state='CA'."
        )

    query = f"{city}, {state}"
    data = await fetch_weather_json(
        LOCATION_SEARCH_URL,
        {
            "query": query,
            "locationType": "city",
            "format": "json",
            "language": "en-US",
        },
    )

    if isinstance(data, str):
        return data

    location_data = data.get("location")

    if not isinstance(location_data, dict):
        return f"No location found for {query}."

    latitude = get_indexed_location_value(location_data, "latitude")
    longitude = get_indexed_location_value(location_data, "longitude")

    if latitude is None or longitude is None:
        return f"No geocode found for {query}."

    return {
        "query": query,
        "city": get_indexed_location_value(location_data, "city"),
        "state": get_indexed_location_value(location_data, "adminDistrictCode")
        or get_indexed_location_value(location_data, "adminDistrict"),
        "country": get_indexed_location_value(location_data, "countryCode"),
        "geocode": f"{latitude},{longitude}",
    }


def parse_forecast_days(forecast_data: dict) -> list[dict]:
    dayparts = forecast_data.get("daypart")

    if not isinstance(dayparts, list) or not dayparts:
        return []

    daypart = dayparts[0]
    day_of_week = forecast_data.get("dayOfWeek")

    if not isinstance(day_of_week, list):
        return []

    forecast_days = min(5, len(day_of_week))
    days = []

    for day_index in range(forecast_days):
        days.append(
            {
                "day": day_of_week[day_index],
                "high_f": get_indexed_weather_value(
                    forecast_data,
                    "temperatureMax",
                    day_index,
                ),
                "low_f": get_indexed_weather_value(
                    forecast_data,
                    "temperatureMin",
                    day_index,
                ),
                "narrative": get_indexed_weather_value(
                    forecast_data,
                    "narrative",
                    day_index,
                )
                or "Forecast narrative unavailable.",
                "day_summary": format_daypart(daypart, day_index * 2),
                "night_summary": format_daypart(daypart, day_index * 2 + 1),
            }
        )

    return days


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

    return {
        "station_id": STATION_ID,
        "neighborhood": observation["neighborhood"],
        "days": parse_forecast_days(forecast_data),
    }


async def get_city_current_conditions_payload(
    city: str,
    state: str,
) -> dict | str:
    location = await resolve_city_state_location(city, state)

    if isinstance(location, str):
        return location

    data = await fetch_weather_json(
        NEAREST_STATION_URL,
        {
            "geocode": location["geocode"],
            "units": "e",
            "numStations": 1,
            "format": "json",
        },
    )

    if isinstance(data, str):
        return data

    observations = data.get("observations")

    if not isinstance(observations, list) or not observations:
        return f"No current conditions found near {location['query']}."

    observation = observations[0]
    obs = observation.get("imperial", {})

    return {
        "location": format_city_state_location(location),
        "neighborhood": observation.get("neighborhood"),
        "station_id": observation.get("stationID"),
        "observed_local": observation.get("obsTimeLocal"),
        "temperature_f": obs.get("temp"),
        "feels_like_f": obs.get("heatIndex"),
        "wind_chill_f": obs.get("windChill"),
        "dew_point_f": obs.get("dewpt"),
        "humidity_percent": observation.get("humidity"),
        "wind_speed_mph": obs.get("windSpeed"),
        "wind_direction_degrees": observation.get("winddir"),
        "wind_gust_mph": obs.get("windGust"),
        "pressure_inhg": obs.get("pressure"),
        "uv": observation.get("uv"),
    }


async def get_city_forecast_payload(city: str, state: str) -> dict | str:
    location = await resolve_city_state_location(city, state)

    if isinstance(location, str):
        return location

    forecast_data = await fetch_weather_json(
        DAILY_FORECAST_URL,
        {
            "geocode": location["geocode"],
            "format": "json",
            "units": "e",
            "language": "en-US",
        },
    )

    if isinstance(forecast_data, str):
        return forecast_data

    return {
        "location": format_city_state_location(location),
        "days": parse_forecast_days(forecast_data),
    }


@mcp.tool()
async def get_station_conditions() -> str:
    """Get current weather conditions for the user's own personal
    weather station.

    Use this for queries like 'what is my weather', 'current
    conditions', or 'how is the weather here'. Do NOT use this
    when the user specifies any city or state.
    """
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
async def get_station_forecast() -> str:
    """Get a 5-day weather forecast for the user's own personal
    weather station.

    Use this for queries like 'what is my forecast', 'will it
    rain this week', or 'forecast for here'. Do NOT use this
    when the user specifies any city or state.
    """
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


@mcp.tool()
async def get_current_conditions_for_city_state(
    city: str,
    state: str = "",
) -> str:
    """Get current weather conditions for a specific city and state.

    Use this whenever the user names a city or state, such as
    'Kyle, TX' or 'Austin, Texas'. Accepts city+state separately
    or combined as 'City, ST' or 'City ST'. Do NOT use this for
    the user's own station.
    """
    conditions = await get_city_current_conditions_payload(city, state)

    if isinstance(conditions, str):
        return conditions

    neighborhood = conditions.get("neighborhood") or ""
    station_id = conditions.get("station_id") or ""
    station_note = (
        f" (nearest station: {neighborhood} {station_id})".rstrip()
        if neighborhood or station_id
        else ""
    )

    return (
        f"Current weather in {conditions['location']}{station_note}\n"
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
        f"UV: {conditions['uv']}"
    )


@mcp.tool()
async def get_forecast_for_city_state(city: str, state: str = "") -> str:
    """Get a 5-day weather forecast for a specific city and state.

    Use this whenever the user names a city or state, such as
    'Kyle, TX' or 'Austin, Texas'. Accepts city+state separately
    or combined as 'City, ST' or 'City ST'. Do NOT use this for
    the user's own station.
    """
    forecast = await get_city_forecast_payload(city, state)

    if isinstance(forecast, str):
        return forecast

    lines = [f"5-day forecast for {forecast['location']}"]

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
