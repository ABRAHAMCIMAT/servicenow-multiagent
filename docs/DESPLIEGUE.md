# Guía de despliegue — Contenedores

> Sistema Multiagente ServiceNow · Fase 1
> Última actualización: 21 de septiembre de 2026 · Versión 2.2.0

Esta guía cubre el despliegue con Docker y Docker Compose. Al terminar la Fase 0,
el sistema **falla al arrancar** si falta configuración de seguridad: es
intencional, un despliegue mal configurado no debe arrancar inseguro.

---

## 1. Requisitos

| Componente | Versión mínima |
|-----------|----------------|
| Docker Engine | 24.0 |
| Docker Compose | v2.20 |
| RAM | 2 GB (4 GB si usas Jan como proveedor LLM) |
| Disco | 1 GB |

Comprueba tu instalación:

```bash
docker --version
docker compose version
```

---

## 2. Arranque rápido

```bash
# 1) Crear el archivo de entorno
cp .env.example .env

# 2) Generar una credencial de API (rol admin)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 3) Editar .env con la credencial generada y el origen permitido
#    API_KEYS=<la-clave-generada>:admin
#    CORS_ORIGINS=http://localhost:8000

# 4) Levantar
docker compose up -d

# 5) Verificar
curl -sf http://localhost:8000/api/health && echo "  OK"
```

Salida esperada del health: `{"status":"ok"}`

---

## 3. Variables obligatorias

Estas dos variables **deben** estar definidas cuando `APP_ENV=production`
(el valor por defecto en la imagen). El contenedor no arranca sin ellas.

| Variable | Formato | Ejemplo |
|----------|---------|---------|
| `API_KEYS` | `clave:rol` separadas por coma | `abc123:admin,def456:agent,ghi789:user` |
| `CORS_ORIGINS` | Lista de orígenes separada por coma | `https://miapp.com,https://admin.miapp.com` |

**Roles disponibles** (jerárquicos: admin ⊃ agent ⊃ user):

| Rol | Puede hacer |
|-----|-------------|
| `user` | `/v1/chat/completions` (conexión de Jan) |
| `agent` | + listar/ver conversaciones, escalar, ver el dashboard |
| `admin` | + eventos crudos de telemetría, `/api/health/detail` |

> ⚠️ **`*` en `CORS_ORIGINS` está prohibido.** El sistema rechaza el comodín al
> arrancar — es un hallazgo crítico corregido en la Fase 0.

---

## 4. Modos de despliegue

### 4.1 Mock (por defecto) — sin infraestructura externa

Ideal para demos y para el pipeline de CI. El LLM es determinista, sin red ni coste.

```bash
docker compose up -d
# LLM_PROVIDER=mock (ya es el valor por defecto en .env.example)
```

### 4.2 Jan como proveedor LLM local

```bash
docker compose --profile live up -d
```

Luego en Jan, configura el proveedor OpenAI-compatible apuntando a
`http://localhost:8000/v1` con una credencial de rol `user`.

### 4.3 ServiceNow real (modo LIVE)

```bash
SNOW_INSTANCE=acme.service-now.com
SNOW_USER=svc_lindy
SNOW_PASSWORD=...        # o SNOW_TOKEN=...
```

> En `production` el adaptador **exige** estar en modo LIVE. Si la configuración
> es parcial, falla al arrancar en lugar de degradar a DEMO en silencio.

### 4.4 OpenAI

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

Sin `LLM_API_KEY` el arranque falla (fail-fast de la Fase 0).

---

## 5. Conectar Jan

1. Levanta el stack y abre Jan.
2. Ajustes → Proveedores → OpenAI compatible.
3. Base URL: `http://localhost:8000/v1`
4. API key: una credencial con rol `user` (el rol más bajo basta).
5. Modelo: `servicenow-multiagent`

Jan podrá conversar con el sistema multiagente. El endpoint responde con el
formato estándar de OpenAI, incluido streaming SSE.

---

## 6. Volúmenes y respaldo

El volumen `snow-data` monta en `/app/data` y contiene:

| Archivo | Contenido |
|---------|-----------|
| `app.log` | Log estructurado JSON (con rotación) |
| `telemetry.jsonl` | Eventos estandarizados (4 dimensiones) |
| `conversations.json` | Estado de las conversaciones |
| `audit.jsonl` | Audit trail append-only de acciones sensibles |

Respaldo:

```bash
docker run --rm -v servicenow-multiagent_snow-data:/data -v "$PWD:/backup" \
  alpine tar czf /backup/snow-data-$(date +%F).tar.gz -C /data .
```

Restauración:

```bash
docker run --rm -v servicenow-multiagent_snow-data:/data -v "$PWD:/backup" \
  alpine sh -c "cd /data && tar xzf /backup/snow-data-FECHA.tar.gz"
```

---

## 7. Operación

| Endpoint | Rol | Uso |
|----------|-----|-----|
| `GET /api/health` | público | Liveness (sin datos sensibles) |
| `GET /api/health/detail` | admin | Diagnóstico de configuración |
| `GET /api/dashboard` | agent | Métricas en 4 dimensiones |
| `GET /api/dashboard/events` | admin | Telemetría cruda |
| `GET /dashboard` | — | Dashboard web (Chart.js) |

Monitoreo típico:

```bash
docker compose ps                       # estado y salud
docker compose logs -f api              # logs en vivo
docker inspect --format '{{.State.Health.Status}}' snow-api
```

---

## 8. Actualización

```bash
git pull
docker compose build
docker compose up -d
```

La imagen es multi-stage, así que el rebuild reutiliza la caché de wheels.

---

## 9. Solución de problemas

| Síntoma | Causa | Solución |
|---------|-------|----------|
| El contenedor muere al arrancar | Falta `API_KEYS` o `CORS_ORIGINS` | Defínelas en `.env` (comportamiento intencional) |
| `CORS_ORIGINS` rechazado | Se usó `*` | Usa orígenes explícitos |
| `RuntimeError: ... requiere su webhook` | `NOTIFY_CHANNEL` sin webhook, en producción | Configura `SLACK_WEBHOOK_URL` o cambia de canal |
| `RuntimeError: ServiceNow debe estar en modo LIVE` | Config parcial en producción | Completa `SNOW_INSTANCE` + `SNOW_USER`/`SNOW_TOKEN`, o usa `APP_ENV=development` |
| 401 en todas las peticiones | Credencial ausente o inválida | Envía `X-API-Key` o `Authorization: Bearer` |
| 403 en un endpoint | Rol insuficiente | Usa una credencial con el rol requerido |
| 429 | Rate limit excedido | Ajusta `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW` |
| El health tarda en estar OK | Arranque de la app | `start_period` de 15 s; espera y reintenta |

---

## 10. Notas de producción

- **Rate limiting:** la implementación actual es en memoria. Con **varias
  réplicas** hay que moverla a Redis para que el límite sea compartido. La
  interfaz (`RateLimiter.check`) está pensada para ese cambio sin tocar endpoints.
- **Secretos:** no los pongas en `docker-compose.yml`. Usa el gestor de secretos
  de tu plataforma (Docker secrets, Kubernetes Secrets, AWS Secrets Manager).
- **TLS:** el contenedor sirve HTTP. Termina TLS en un proxy inverso
  (nginx, Traefik, ALB) por delante.
- **Rotación de logs:** `app.log` rota a 5 MB × 5 archivos. El resto de archivos
  de `data/` requieren logrotate externo.
- **Auditoría:** `audit.jsonl` es append-only por diseño. El actor se identifica
  por el hash de su credencial, nunca por la clave.
