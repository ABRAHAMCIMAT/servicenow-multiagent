"""
Configuracion centralizada por entorno (Fase 0).

Sustituye las rutas absolutas hardcodeadas (/agent/task/...) por rutas
relativas a DATA_DIR, configurable por variable de entorno. Tambien valida
la configuracion critica al arranque (fail-fast): CORS obligatorio y sin
comodines en produccion.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_ENV = os.getenv("APP_ENV", "development")

# Raiz de datos: relativa y configurable. Por defecto, backend/data del proyecto.
_PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(_PROJECT_ROOT / "data")))

LOG_FILE = os.getenv("LOG_FILE", "") or str(DATA_DIR / "app.log")
TELEMETRY_LOG = os.getenv("TELEMETRY_LOG", "") or str(DATA_DIR / "telemetry.jsonl")
CONV_STORE = os.getenv("CONV_STORE", "") or str(DATA_DIR / "conversations.json")
AUDIT_LOG = os.getenv("AUDIT_LOG", "") or str(DATA_DIR / "audit.jsonl")

IS_PRODUCTION = APP_ENV == "production"

# CORS: lista blanca explicita. En produccion debe definirse siempre.
_cors = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _cors.split(",") if o.strip()]
if not CORS_ORIGINS:
    if IS_PRODUCTION:
        raise RuntimeError("CORS_ORIGINS es obligatoria en produccion.")
    # Solo en desarrollo se permite localhost; nunca "*".
    CORS_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]

if "*" in CORS_ORIGINS:
    raise RuntimeError("CORS_ORIGINS no admite el comodin '*'.")


def ensure_dirs() -> None:
    """Crea el directorio de datos si no existe."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
