"""
Configuración compartida de pytest.

Fuerza LLM_PROVIDER=mock y redirige logs/telemetría/conversaciones a un
directorio temporal ANTES de que cualquier test importe `backend.server` —
sus singletons de módulo (store, telemetry, metrics_engine, ...) se
construyen una sola vez, en el momento del import, leyendo estas variables
de entorno. Si se fijaran dentro de un fixture, ya sería tarde: el import ya
habría ocurrido con los defaults (que apuntan a `backend/data/`, los
archivos reales del proyecto — no queremos que la suite de tests los ensucie).
"""
from __future__ import annotations

import os
import tempfile

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="sn_multiagent_tests_")
os.environ["LLM_PROVIDER"] = "mock"
os.environ.setdefault("LOG_FILE", os.path.join(_TEST_DATA_DIR, "app.log"))
os.environ.setdefault("CONV_STORE", os.path.join(_TEST_DATA_DIR, "conversations.json"))
os.environ.setdefault("TELEMETRY_LOG", os.path.join(_TEST_DATA_DIR, "telemetry.jsonl"))
os.environ.setdefault("API_KEY", "")
