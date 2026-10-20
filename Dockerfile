
FROM node:22-alpine AS client-build
WORKDIR /app/client
COPY client/package*.json ./
RUN npm install
COPY client/ ./
RUN npm run build


FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY server/ ./server/


WORKDIR /app/server
RUN uv sync --frozen --no-dev


COPY --from=client-build /app/client/dist /app/client/dist

ENV PORT=7860
EXPOSE 7860


CMD ["sh", "-c", "uv run uvicorn mp.main:app --host 0.0.0.0 --port ${PORT}"]
