FROM node:24-bookworm-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.13.6 AS uv
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 media && useradd -u 10001 -g media -M media \
    && install -d -o media -g media /data
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=web /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-group ui
COPY backend/ ./backend/
COPY --from=web /web/dist ./frontend/dist/
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/backend DATA_DIR=/data PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "service.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
