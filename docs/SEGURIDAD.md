# Seguridad — Fase 0

Documentación de la capa de seguridad introducida en la Fase 0 del roadmap LLMOps.

## Autenticación

Todos los endpoints (excepto `/api/health`) requieren credencial:

```
Authorization: Bearer <API_KEY>
```
o
```
X-API-Key: <API_KEY>
```

Las claves se configuran en la variable de entorno `API_KEYS` con el formato
`clave:rol,clave:rol`:

```bash
API_KEYS="k_admin_xxx:admin,k_agent_yyy:agent,k_user_zzz:user"
```

- Si `API_KEYS` está vacía y `APP_ENV != production`, se genera una clave de
  desarrollo (rol admin) y se imprime **una sola vez** en consola.
- En producción, `API_KEYS` vacía hace que el servidor **no arranque** (fail-fast).

## Roles (RBAC)

| Rol | Alcance |
|-----|---------|
| `user` | `/v1/chat/completions` (integraciones tipo Jan) |
| `agent` | consultar conversaciones, escalar, ver dashboard |
| `admin` | eventos crudos de telemetría, health detallado |

El actor se identifica en logs y auditoría por el **hash** de su credencial
(`key_id`), nunca por la clave.

## Rate limiting

Límite por ventana deslizante: `60 solicitudes / 60 s` por credencial
(configurable con `RATE_LIMIT_MAX` y `RATE_LIMIT_WINDOW`). Las peticiones
anonimas se limitan por IP.

Respuesta al exceder el límite:

```json
HTTP/1.1 429 Too Many Requests
Retry-After: 42
{"detail": "Demasiadas solicitudes. Intente mas tarde."}
```

> **Nota:** el contador vive en memoria. Con varias réplicas debe moverse a
> Redis (misma interfaz `RateLimiter.check`), previsto para la Fase 4.

## Redacción de PII

Los logs y la telemetría redactan automáticamente:

| Tipo | Ejemplo | Resultado |
|------|---------|-----------|
| Email | `ana@corp.com` | `[REDACTED:email]` |
| Teléfono | `+52 81 1234 5678` | `[REDACTED:phone]` |
| Tarjeta | `4111 1111 1111 1111` | `[REDACTED:card]` |
| IPv4 | `10.0.0.15` | `[REDACTED:ipv4]` |
| SSN | `123-45-6789` | `[REDACTED:ssn]` |

El mensaje crudo del usuario **nunca** se persiste en logs. Hay dos capas:

1. **Supresión por defecto** — `preview()` omite el contenido del usuario y
   escribe `[contenido del usuario omitido]`. Solo si se activa
   `LOG_USER_CONTENT=true` (depuración local) se registra, ya redactado.
2. **Redacción en el formateador** — el `JsonFormatter` aplica `redact_text()`
   a cada mensaje como defensa en profundidad, aunque el llamador lo olvide.

## Audit trail

`backend/data/audit.jsonl` (append-only) registra acciones sensibles:

| Acción | Cuándo |
|--------|--------|
| `chat.received` | cada mensaje aceptado |
| `chat.rejected` | entrada bloqueada por guardrails |
| `escalate` | escalación a Nivel 2/3 |

Cada entrada incluye `ts`, `action`, `actor` (hash), `target`, `outcome` y
`metadata`. La rotación se gestiona fuera del proceso (logrotate).

## CORS

Lista blanca explícita en `CORS_ORIGINS` (separada por comas):

```bash
CORS_ORIGINS="https://soporte.corp.com,https://portal.corp.com"
```

- El comodín `*` está **prohibido**: el arranque falla si se usa.
- En producción `CORS_ORIGINS` es obligatoria.
- En desarrollo, por defecto se permite solo `localhost:8000`.

## Variables de entorno de seguridad

| Variable | Default | Descripción |
|----------|---------|-------------|
| `APP_ENV` | `development` | `production` activa los fail-fast |
| `API_KEYS` | — | Credenciales en formato `clave:rol` |
| `CORS_ORIGINS` | localhost (dev) | Orígenes permitidos |
| `RATE_LIMIT_MAX` | `60` | Solicitudes por ventana |
| `RATE_LIMIT_WINDOW` | `60` | Ventana en segundos |
| `AUDIT_LOG` | `backend/data/audit.jsonl` | Ruta del audit trail |
| `LOG_USER_CONTENT` | `false` | Si `true`, registra el contenido del usuario redactado (solo depuración) |

## Verificación rápida

```bash
# 401 sin credencial
curl -i -X POST localhost:8000/api/chat -H 'Content-Type: application/json' -d '{"message":"hola"}'

# 200 con credencial
curl -i -X POST localhost:8000/api/chat -H "X-API-Key: $KEY" \
     -H 'Content-Type: application/json' -d '{"message":"no puedo entrar al CRM"}'
```
