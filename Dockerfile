FROM --platform=$BUILDPLATFORM ghcr.io/astral-sh/uv:latest AS uv

FROM ubuntu:24.04

RUN apt-get update \
	&& DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
		ca-certificates \
		caddy \
		python3 \
		python3-venv \
	&& rm -rf /var/lib/apt/lists/* \
	&& useradd --create-home --shell /usr/sbin/nologin app \
	&& mkdir -p /app /data /config /home/app/.cache/uv \
	&& chown -R app:app /app /data /config /home/app

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /app

ENV HTTP_PORT=8443 \
	HOME=/home/app \
	XDG_CONFIG_HOME=/config \
	XDG_DATA_HOME=/data \
	UV_CACHE_DIR=/home/app/.cache/uv \
	MCP_TRANSPORT=sse \
	MCP_HOST=127.0.0.1 \
	MCP_PORT=8000 \
	MCP_SSE_PATH=/sse \
	MCP_MESSAGE_PATH=/messages/ \
	MCP_STREAMABLE_HTTP_PATH=/mcp \
	MCP_ALLOWED_HOSTS=localhost:*,127.0.0.1:*,10.0.0.37:* \
	MCP_ALLOWED_ORIGINS=http://localhost:*,http://127.0.0.1:*,http://10.0.0.37:* \
	HA_API_HOST=127.0.0.1 \
	HA_API_PORT=8001 \
	UV_COMPILE_BYTECODE=1 \
	UV_LINK_MODE=copy

COPY pyproject.toml ./
RUN uv sync --python /usr/bin/python3 --no-dev --no-install-project

COPY Caddyfile docker-entrypoint.sh ha_api_server.py wunderground_server.py ./

RUN chmod +x docker-entrypoint.sh \
	&& chown -R app:app /app

USER app

EXPOSE 8443

ENTRYPOINT ["./docker-entrypoint.sh"]