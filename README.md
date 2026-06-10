# Weather Underground MCP Server

This repository provides a small Model Context Protocol (MCP) server for Weather
Underground / Weather.com personal weather station data. It exposes tools for
current local conditions and a 5-day forecast for a configured station.

The server is implemented with `FastMCP`. It can run from VS Code MCP
configuration over stdio, or from Docker as an HTTP SSE service for Home
Assistant.

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

## Install Dependencies

This project uses `uv` to install and run Python dependencies from
`pyproject.toml`.

Install `uv` if it is not already available:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install the project dependencies:

```sh
uv sync
```

The dependencies installed by `uv sync` are:

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
| `MCP_TRANSPORT` | No | MCP transport. Defaults to `stdio`; Docker sets this to `sse` for Home Assistant. Use `streamable-http` for clients that support that transport. |
| `MCP_HOST` | No | HTTP bind host used by FastMCP. Defaults to `127.0.0.1`. |
| `MCP_PORT` | No | HTTP bind port used by FastMCP. Defaults to `8000`. |
| `MCP_SSE_PATH` | No | SSE MCP path used by Home Assistant. Defaults to `/sse`. |
| `MCP_MESSAGE_PATH` | No | SSE client-to-server message path. Defaults to `/messages/`. |
| `MCP_STREAMABLE_HTTP_PATH` | No | Streamable HTTP MCP path. Defaults to `/mcp`. |
| `MCP_ALLOWED_HOSTS` | No | Comma-separated Host headers allowed by FastMCP DNS rebinding protection. Defaults include `10.0.0.37:*`. |
| `MCP_ALLOWED_ORIGINS` | No | Comma-separated Origin headers allowed by FastMCP DNS rebinding protection. Defaults include `http://10.0.0.37:*`. |
| `HTTP_PORT` | No | HTTP port exposed by Caddy in Docker. Defaults to `8443`. |

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

## Docker HTTP Service for Home Assistant

Build the Ubuntu `linux/amd64` Docker image:

```sh
docker buildx build --platform linux/amd64 -t wunderground-mcp .
```

Run it as a fully contained HTTP service:

```sh
docker run --rm \
	-p 8443:8443 \
	-e MCP_ALLOWED_HOSTS="localhost:*,127.0.0.1:*,10.0.0.37:*" \
	-e MCP_ALLOWED_ORIGINS="http://localhost:*,http://127.0.0.1:*,http://10.0.0.37:*" \
	-e WU_API_KEY="your-api-key" \
	-e WU_STATION_ID="your-station-id" \
	wunderground-mcp
```

The MCP SSE endpoint is available at:

```text
http://10.0.0.37:8443/sse
```

Enter that URL as the Home Assistant MCP integration's **SSE Server URL**. Home
Assistant currently supports MCP tools over SSE, not streamable HTTP, so Docker
defaults `MCP_TRANSPORT` to `sse`.

The image runs FastMCP on localhost inside the container and uses Caddy as the
public HTTP reverse proxy.

## Home Assistant Forecast Entities

If your current weather sensors already exist in Home Assistant, only add
forecast sensors from this endpoint:

```text
http://10.0.0.37:8443/ha/forecast
```

If your `configuration.yaml` has `sensor: !include sensors.yaml`, add these
entries to `sensors.yaml`:

```yaml
- platform: rest
  name: wunderground_forecast_today
  unique_id: wunderground_forecast_today
  resource: http://10.0.0.37:8443/ha/forecast
  scan_interval: 1800
  value_template: "{{ value_json.days[0].narrative }}"
  json_attributes_path: "$.days[0]"
  json_attributes:
    - day
    - high_f
    - low_f
    - day_summary
    - night_summary

- platform: rest
  name: wunderground_forecast_tomorrow
  unique_id: wunderground_forecast_tomorrow
  resource: http://10.0.0.37:8443/ha/forecast
  scan_interval: 1800
  value_template: "{{ value_json.days[1].narrative }}"
  json_attributes_path: "$.days[1]"
  json_attributes:
    - day
    - high_f
    - low_f
    - day_summary
    - night_summary
```

If your sensors are defined directly in `configuration.yaml`, put those same
entries under your existing top-level `sensor:` key. After restarting Home
Assistant, expose `sensor.wunderground_forecast_today` and
`sensor.wunderground_forecast_tomorrow` to Assist.

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
├── .dockerignore
├── Caddyfile
├── Dockerfile
├── README.md
├── docker-entrypoint.sh
├── ha_api_server.py
├── pyproject.toml
└── wunderground_server.py
```

`wunderground_server.py` contains the MCP server and Weather.com API calls.
`ha_api_server.py` exposes JSON endpoints for Home Assistant REST sensors.
`pyproject.toml` defines the Python version and package dependencies.
`Dockerfile`, `Caddyfile`, and `docker-entrypoint.sh` package the server as an
HTTP container service.

## Notes

- The server uses imperial units (`units=e`) by default.
- If the current day's daytime forecast has already passed, Weather.com may
	return no high temperature for that day. The server displays that as
	`unavailable`.
- API keys should be stored in MCP environment configuration or shell
	environment variables, not committed to this repository.
