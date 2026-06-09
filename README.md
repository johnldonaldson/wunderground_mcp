# Weather Underground MCP Server

This repository provides a small Model Context Protocol (MCP) server for Weather
Underground / Weather.com personal weather station data. It exposes tools for
current local conditions and a 5-day forecast for a configured station.

The server is implemented with `FastMCP` and is intended to run from VS Code MCP
configuration over stdio.

## Features

- Current conditions for a configured Weather Underground personal weather
	station.
- Expanded current observation details, including temperature, feels-like
	temperature, humidity, wind, gusts, pressure, precipitation, solar radiation,
	UV, elevation, and QC status.
- 5-day daily forecast based on the configured station's latitude and longitude.
- Forecast summaries include high/low temperatures, narrative text, day/night
	conditions, precipitation chance, and wind descriptions.

## Requirements

- macOS, Linux, or Windows with Python support.
- Python `>=3.12`.
- `uv` installed and available on your `PATH`.
- A Weather Underground / Weather.com API key with access to:
	- `https://api.weather.com/v2/pws/observations/current`
	- `https://api.weather.com/v3/wx/forecast/daily/5day`
- A Weather Underground personal weather station ID, for example
	`KCAHUNTI63`.

Python package dependencies are managed in `pyproject.toml`:

```toml
dependencies = [
		"httpx>=0.28.1",
		"mcp[cli]>=1.27.2",
]
```

## Environment Variables

The server reads these environment variables:

| Variable | Required | Description |
| --- | --- | --- |
| `WU_API_KEY` | Yes | Weather Underground / Weather.com API key. |
| `WU_STATION_ID` | No | Personal weather station ID. Defaults to `KCAHUNTI63`. |

## VS Code MCP Configuration

Add a server entry like this to your VS Code `mcp.json` file. Replace the path
and credentials with your own values.

```json
{
	"servers": {
		"weather-underground": {
			"type": "stdio",
			"command": "uv",
			"args": [
				"--directory",
				"/path/to/wunderground",
				"run",
				"wunderground_server.py"
			],
			"env": {
				"WU_API_KEY": "your-api-key",
				"WU_STATION_ID": "your-station-id"
			}
		}
	}
}
```

After changing the server code or MCP configuration, restart or reload the MCP
server in VS Code so newly added tools are discovered.

## Available MCP Tools

### `get_current_conditions`

Returns the latest current observation for the configured station.

Example output:

```text
Current weather in Cascade Lane (Station ID: KCAHUNTI63)
Observed local: 2026-06-09 16:09:40
Temperature: 76F
Feels like: 76F
Wind chill: 76F
Dew point: 64F
Humidity: 68%
Wind: 3 mph from 191 degrees
Wind gust: 7 mph
Pressure: 29.82 inHg
Precip rate: 0.0 in/hr
Precip total: 0.0 in
Solar radiation: 422.4
UV: 4.0
Elevation: 43 ft
QC status: 1
```

### `get_forecast`

Returns a 5-day forecast for the configured station. The server first retrieves
the station's current observation, uses its latitude and longitude, then requests
the daily forecast endpoint.

Example output:

```text
5-day forecast for Cascade Lane (Station ID: KCAHUNTI63)

Tuesday: High unavailable / Low 63F
Summary: Partly cloudy. Lows overnight in the low 60s.
Tonight: Partly Cloudy, precip 20%, Winds S at 10 to 15 mph.

Wednesday: High 77F / Low 64F
Summary: Mostly sunny. Highs in the upper 70s and lows in the mid 60s.
Tomorrow: Mostly Sunny, precip 20%, Winds SSW at 10 to 15 mph.
Tomorrow night: Partly Cloudy, precip 11%, Winds SSE at 5 to 10 mph.
```

## Local Development

Install dependencies with `uv`:

```sh
uv sync
```

Run the MCP server directly:

```sh
WU_API_KEY="your-api-key" WU_STATION_ID="KCAHUNTI63" uv run wunderground_server.py
```

Run a direct current-conditions check:

```sh
WU_API_KEY="your-api-key" WU_STATION_ID="KCAHUNTI63" \
	uv run python -c 'import asyncio, wunderground_server; print(asyncio.run(wunderground_server.get_current_conditions()))'
```

Run a direct forecast check:

```sh
WU_API_KEY="your-api-key" WU_STATION_ID="KCAHUNTI63" \
	uv run python -c 'import asyncio, wunderground_server; print(asyncio.run(wunderground_server.get_forecast()))'
```

## Project Structure

```text
.
├── README.md
├── pyproject.toml
└── wunderground_server.py
```

`wunderground_server.py` contains the MCP server and Weather.com API calls.
`pyproject.toml` defines the Python version and package dependencies.

## Notes

- The server uses imperial units (`units=e`) by default.
- If the current day's daytime forecast has already passed, Weather.com may
	return no high temperature for that day. The server displays that as
	`unavailable`.
- API keys should be stored in MCP environment configuration or shell
	environment variables, not committed to this repository.
