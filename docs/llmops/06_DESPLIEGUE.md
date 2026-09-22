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

# 2. Configurar variables de entorno (ver .env.example — 23 variables documentadas)
cp .env.example .env
# editar .env: LLM_PROVIDER, API_KEY (recomendado fuera de localhost), etc.

# 3. Levantar el servidor
python3 -m backend.server
```

## Despliegue con Docker (recomendado)
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python3", "-m", "backend.server"]
```

## Operación y mantenimiento

### Integración continua
`.github/workflows/ci.yml` corre en cada push/PR: instala dependencias,
verifica que todo el código compile, ejecuta la suite de `pytest`
(`tests/`) y el test set de evaluación (`scripts/run_evals.py`). Ningún
cambio llega a `main` sin pasar estos tres pasos.

### Monitoreo
- **Logs estructurados** en JSON para integración con ELK/Datadog.
- **Telemetría** para el dashboard de 4 dimensiones.
- **Langfuse** para observabilidad LLM nativa.

### Alertas recomendadas
| Alerta | Umbral | Acción |
|--------|--------|--------|
| Tasa de error LLM | > 5% | Revisar proveedor, reintentos |
| Latencia E2E | > 30s | Revisar cuellos de botella por agente |
| Costo diario | > umbral | Revisar consumo de tokens |
| Tasa de escalación | > 20% | Revisar calidad de autoservicio |

### Backup y recuperación
- **Telemetría**: archivo JSONL con rotación.
- **Conversaciones**: persistencia en `backend/data/conversations.json`.
- **Logs**: rotación automática (5 MB × 5) — pero **solo si el proceso
  escribe a `LOG_FILE`** (`RotatingFileHandler`, ver `llmops/logging.py`).
  Si en cambio se redirige la salida estándar a mano
  (`python3 -m backend.server > server.out`), ese archivo **no rota** — crece
  sin límite y el `RotatingFileHandler` no lo toca. Usa `LOG_FILE` en vez de
  redirigir stdout, o delega la rotación a un supervisor de procesos
  (systemd/`journald`, supervisord) si necesitas capturar stdout igual.

## Escalado
- El sistema es **stateless** por conversación (estado en memoria/JSON).
- Para escalar: mover el estado a una base de datos (Redis/Postgres)
  implementando `ConversationStorage` (`backend/core/storage.py` — un
  `Protocol` con `create`/`get`/`update`/`list`) y sustituyendo la
  instancia `ConversationStore` por la nueva en `server.py`; el resto del
  sistema no cambia, ya que `server.py` ya está tipado contra la interfaz,
  no contra la clase concreta.
- Los agentes son **independientes** y pueden ejecutarse en paralelo.
