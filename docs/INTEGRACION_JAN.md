# Integración con Jan

Jan (github.com/janhq/jan) es un frontend de chat open-source que ejecuta LLMs localmente con privacidad. Este sistema multiagente se integra con Jan de dos formas complementarias:

## Opción A: Jan como proveedor de LLM para los agentes

El backend usa Jan como motor de razonamiento de los agentes. Jan expone un **servidor local compatible con OpenAI** en `http://localhost:1337/v1`.

1. Abre Jan → **Settings → Advanced → Local API Server** → activa el servidor.
2. Descarga un modelo (p. ej. `gpt-oss:latest`) desde el Hub de Jan.
3. Ejecuta el backend apuntando a Jan:

```bash
export LLM_PROVIDER=jan
export LLM_BASE_URL=http://localhost:1337/v1
export LLM_MODEL=gpt-oss:latest
./scripts/run_live.sh
```

Los agentes (clasificador, diagnóstico, etc.) usarán el modelo local de Jan para razonar, manteniendo los datos en tu máquina.

## Opción B: Jan como frontend del sistema multiagente

El backend expone un **endpoint compatible con OpenAI** en `http://localhost:8000/v1/chat/completions`. Jan puede conectarse a él como un proveedor personalizado:

1. Ejecuta el backend: `./scripts/run_demo.sh` (o `run_live.sh`).
2. En Jan, añade un **proveedor personalizado** (Settings → Advanced → OpenAI-compatible API):
   - **Base URL:** `http://localhost:8000/v1`
   - **API Key:** `jan` (cualquier valor)
   - **Model:** `servicenow-multiagent`
3. Selecciona el modelo en el chat de Jan y conversa con el sistema multiagente.

Cada mensaje que envíes a Jan se enruta al orquestador, que ejecuta el flujo multiagente completo y devuelve la respuesta.

## Opción C: Frontend web incluido (estilo Jan)

El proyecto incluye un frontend web (`frontend/index.html`) con la estética de Jan (tema oscuro, sidebar de agentes, chat conversacional). Es la forma más rápida de ver el sistema en acción:

```bash
./scripts/run_demo.sh
# en otra terminal:
python3 -m http.server 8080 --directory frontend
# abre http://localhost:8080
```

## Resumen de puertos

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| Jan Local API | 1337 | LLM local de Jan |
| Backend multiagente | 8000 | API REST + endpoint OpenAI-compatible |
| Frontend web | 8080 | Chat web (estilo Jan) |
