# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# Vision One / MCP traffic is all outbound HTTPS; no compiler toolchain needed at runtime.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

USER appuser

ENV MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"MCP_PORT\",\"8000\")}/healthz', timeout=3).status==200 else 1)"

ENTRYPOINT ["python", "-m", "vision_one_mcp.server"]
