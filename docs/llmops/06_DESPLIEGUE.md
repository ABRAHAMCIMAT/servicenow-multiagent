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

# 2. Configurar variables de entorno
export LLM_PROVIDER="jan"          # jan | openai | mock
export LLM_BASE_URL="http://localhost:1337/v1"
export LLM_MODEL="gpt-oss:latest"
export LOG_LEVEL="INFO"
export LOG_FILE="/var/log/servicenow-multiagent/app.log"

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
- **Logs**: rotación automática (5 MB × 5).

## Escalado
- El sistema es **stateless** por conversación (estado en memoria/JSON).
- Para escalar: mover el estado a una base de datos (Redis/Postgres).
- Los agentes son **independientes** y pueden ejecutarse en paralelo.
