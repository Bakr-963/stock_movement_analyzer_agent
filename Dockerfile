FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md LICENSE langgraph.json .env.example ./
COPY src/ ./src/

RUN python -m pip install --no-cache-dir .

ENTRYPOINT ["stock-movement-analyzer"]
CMD ["--help"]