"""
Rutas de datos compartidas.

Resueltas relativas a `backend/` (usando `__file__`), no al directorio de
trabajo actual, para que los defaults de LOG_FILE / CONV_STORE / TELEMETRY_LOG
funcionen sin importar desde dónde se invoque `python -m backend.server` o
los scripts de `scripts/`.
"""
from __future__ import annotations

import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BACKEND_DIR, "data")


def data_path(filename: str) -> str:
    """Ruta absoluta dentro de `backend/data/` para el archivo dado."""
    return os.path.join(DATA_DIR, filename)
