#!/bin/sh
set -eu

.venv/bin/python wunderground_server.py &
server_pid=$!

.venv/bin/python -m uvicorn ha_api_server:app --host "${HA_API_HOST:-127.0.0.1}" --port "${HA_API_PORT:-8001}" &
ha_api_pid=$!

caddy run --config /app/Caddyfile --adapter caddyfile &
caddy_pid=$!

shutdown() {
	kill "$server_pid" "$ha_api_pid" "$caddy_pid" 2>/dev/null || true
	wait "$server_pid" "$ha_api_pid" "$caddy_pid" 2>/dev/null || true
}

trap shutdown INT TERM

while :; do
	if ! kill -0 "$server_pid" 2>/dev/null; then
		wait "$server_pid"
		exit_code=$?
		shutdown
		exit "$exit_code"
	fi

	if ! kill -0 "$ha_api_pid" 2>/dev/null; then
		wait "$ha_api_pid"
		exit_code=$?
		shutdown
		exit "$exit_code"
	fi

	if ! kill -0 "$caddy_pid" 2>/dev/null; then
		wait "$caddy_pid"
		exit_code=$?
		shutdown
		exit "$exit_code"
	fi

	sleep 1
done