"""
Logging estructurado (JSON) — mejores prácticas LLMOps.

Proporciona un logger con salida JSON estructurada, niveles de severidad,
contexto por conversación/traza y rotación de archivos. Permite correlacionar
todos los eventos de una conversación multiagente y alimentar herramientas de
observabilidad (ELK, Datadog, Langfuse, etc.).

Uso:
    from backend.llmops.logging import get_logger
    log = get_logger("coordinador")
    log.info("conversación iniciada", extra={"conversation_id": "abc", "intent": "incident"})
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional


class JsonFormatter(logging.Formatter):
    """Formatea los registros como objetos JSON de una sola línea."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Añadir contexto extra (conversation_id, trace_id, agent, etc.)
        for key in ("conversation_id", "trace_id", "agent", "intent",
                    "duration_ms", "status", "model", "provider", "tokens"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_output: bool = True,
) -> None:
    """Configura el logging global del sistema.

    Args:
        level: Nivel mínimo de severidad (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Ruta opcional a un archivo de log (con rotación).
        json_output: Si True, emite JSON estructurado; si False, texto plano.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Limpiar handlers existentes para evitar duplicados
    for h in root.handlers[:]:
        root.removeHandler(h)

    formatter = JsonFormatter() if json_output else logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    # Handler de consola
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Handler de archivo con rotación
    if log_file:
        try:
            from logging.handlers import RotatingFileHandler
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            fh = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=5)
            fh.setFormatter(formatter)
            root.addHandler(fh)
        except Exception:
            pass  # el logging nunca debe romper el flujo principal


def get_logger(name: str) -> logging.Logger:
    """Obtiene un logger con el nombre del módulo/agente."""
    return logging.getLogger(name)


# Configurar logging por defecto al importar
if not logging.getLogger().handlers:
    setup_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=os.getenv("LOG_FILE"),
    )
