FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Instala uv a partir da imagem oficial
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copia arquivos de definição de dependências
COPY pyproject.toml README.md /app/

# Instala dependências de produção
RUN uv sync --frozen --no-dev || uv sync --no-dev

# Adiciona ambiente virtual ao PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copia código-fonte e migrações
COPY alembic.ini /app/
COPY alembic /app/alembic
COPY app /app/app

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
