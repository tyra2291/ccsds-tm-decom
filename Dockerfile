# ---- Stage 1: build dependencies with Poetry ----
FROM python:3.14-slim AS builder

RUN pip install --no-cache-dir "poetry>=2.0,<3.0"
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --without dev

# ---- Stage 2: runtime image ----
FROM python:3.14-slim AS runtime

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml poetry.lock ./
COPY src/ ./src/
COPY db/ ./db/

RUN pip install --no-cache-dir -e . --no-deps

EXPOSE 8000

CMD ["uvicorn", "ccsds_tm_decom.api.app:app", "--host", "0.0.0.0", "--port", "8000"]