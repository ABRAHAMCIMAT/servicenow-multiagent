# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Etapa 1: builder — compila las dependencias en wheels
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---------------------------------------------------------------------------
# Etapa 2: runtime — imagen final minima
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    DATA_DIR=/app/data \
    PORT=8000

# Usuario sin privilegios (defensa en profundidad)
RUN groupadd --system --gid 1001 lindy \
 && useradd --system --uid 1001 --gid lindy --home /app --shell /usr/sbin/nologin lindy

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
 && rm -rf /wheels

COPY --chown=lindy:lindy backend/ ./backend/
COPY --chown=lindy:lindy frontend/ ./frontend/
COPY --chown=lindy:lindy dashboard/ ./dashboard/

RUN mkdir -p /app/data && chown -R lindy:lindy /app

USER lindy

EXPOSE 8000

# /api/health es publico por diseno (Fase 0): no expone configuracion sensible
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,sys,urllib.request; \
u=f\"http://127.0.0.1:{os.getenv('PORT','8000')}/api/health\"; \
sys.exit(0 if urllib.request.urlopen(u, timeout=4).status == 200 else 1)"

CMD ["python", "-m", "backend.server"]
