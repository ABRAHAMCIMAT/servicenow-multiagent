# Fase 6 — Despliegue y Operación

## Modos de ejecución
| Modo | Descripción | Uso |
|------|-------------|-----|
| **DEMO** | Sin credenciales, determinista | Validación y desarrollo |
| **LIVE** | Con ServiceNow/AD/notificaciones reales | Producción |

## Despliegue local
```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar variables de entorno (ver .env.example)
cp .env.example .env
# editar .env: LLM_PROVIDER, API_KEYS/CORS_ORIGINS (obligatorias si APP_ENV=production), etc.

# 3. Levantar el servidor
python3 -m backend.server
```

## Despliegue con Docker (recomendado)
Imagen multi-stage real del proyecto (`Dockerfile`): builder con wheels +
runtime `python:3.12-slim`, usuario sin privilegios (`lindy`), healthcheck
integrado sobre `/api/health`, < 300 MB.

```bash
cp .env.example .env   # o exporta API_KEYS/CORS_ORIGINS a mano
docker compose up --build
```

`docker-compose.yml` exige `API_KEYS` y `CORS_ORIGINS` (`${VAR:?mensaje}` —
el compose falla al arrancar si faltan). Ver `docker-compose.override.yml`
para desarrollo local.

## Operación y mantenimiento

### Integración continua
`.github/workflows/ci.yml` corre en cada push/PR: `ruff check`/`ruff format
--check` + `mypy` (lint y tipos), la suite de `pytest` con cobertura en
Python 3.11 y 3.12 (gate: 70% mínimo), `bandit` + `pip-audit` (seguridad), y
un build + smoke test de la imagen Docker (arranca el contenedor, verifica
`/api/health`, verifica que `/api/chat` responda 401 sin credencial y 200
con una válida). `.github/dependabot.yml` mantiene actualizadas las
dependencias de pip y las GitHub Actions.

### Monitoreo
- **Logs estructurados** en JSON para integración con ELK/Datadog — sin PII
  cruda (redacción automática, ver Fase 7).
- **Telemetría** para el dashboard de 4 dimensiones (buffer acotado por
  `TELEMETRY_MAX_EVENTS`).
- **Audit trail** (`DATA_DIR/audit.jsonl`) de acciones sensibles: chat
  recibido/rechazado, escalaciones, generación de matrices de pruebas.
- **Langfuse** para observabilidad LLM nativa.

### Alertas recomendadas
| Alerta | Umbral | Acción |
|--------|--------|--------|
| Tasa de error LLM | > 5% | Revisar proveedor, reintentos |
| Latencia E2E | > 30s | Revisar cuellos de botella por agente |
| Costo diario | > umbral | Revisar consumo de tokens |
| Tasa de escalación | > 20% | Revisar calidad de autoservicio |

### Backup y recuperación
- **Telemetría**: archivo JSONL en `DATA_DIR`, buffer en memoria acotado
  (`TELEMETRY_MAX_EVENTS`), el archivo en disco es append-only completo.
- **Conversaciones**: persistencia en `DATA_DIR/conversations.json`.
- **Audit log**: `DATA_DIR/audit.jsonl`, append-only, nunca se sobrescribe.
- **Logs**: rotación automática (5 MB × 5) — solo si el proceso escribe a
  `LOG_FILE`; si en cambio se redirige stdout a mano, no rota.

## Escalado
- El sistema es **stateless** por conversación (estado en memoria/JSON).
- Para escalar: mover el estado a una base de datos (Redis/Postgres)
  implementando `ConversationStorage` (`backend/core/storage.py` — un
  `Protocol` con `create`/`get`/`update`/`list`) y sustituyendo la
  instancia `ConversationStore` por la nueva en `server.py`; el resto del
  sistema no cambia, ya que `server.py` ya está tipado contra la interfaz,
  no contra la clase concreta.
- Los agentes son **independientes** y pueden ejecutarse en paralelo.
- El rate limiter (`backend/security/rate_limit.py`) es en memoria: con
  varias réplicas necesita moverse a un backend compartido (Redis).
