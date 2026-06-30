# Plan de Migración — BuscaChat Telegram: Zavu → Telegram Directo

## Objetivo

Eliminar Zavu como intermediario y conectar el bot directamente con la Telegram Bot API. Mantener funcionalidades actuales, corregir fotos, habilitar botones inline, reducir costos.

## Principios

1. No reescribir lógica de negocio
2. Cambiar únicamente la capa de transporte
3. Mantener rollback posible en cada fase
4. Probar cada fase antes de continuar
5. Mantener bot funcionando durante la migración

## Arquitectura Actual vs Objetivo

### Actual

```
Telegram → Zavu → FastAPI (/webhook) → zavu_router → zavu_handlers → zavu_client → Zavu → Telegram
```

### Objetivo

```
Telegram → FastAPI (/webhook) → telegram_router → telegram_handlers → python-telegram-bot → Telegram
```

---

## Prerequisitos (antes de empezar)

| # | Prerequisito | Esfuerzo | Bloquea |
|---|---|---|---|
| 1 | Validar `TELEGRAM_BOT_TOKEN` con `getMe` | Trivial | Fase A |
| 2 | Configurar `PUBLIC_BASE_URL` en Railway | Trivial | setWebhook |
| 3 | Agregar `TELEGRAM_ENABLED` feature flag a config | Trivial | Rollback sin redeploy |
| 4 | Persistir FSM (`ReportStateMachine._states`) a SQLite | Pequeño | State entre deploys |
| 5 | Agregar tabla `conversation_state` en database.py | Pequeño | FSM persistente |

---

## Fase A — Fundación

**Objetivo**: Crear infraestructura Telegram y desacoplar handlers del formato Zavu.

**Tiempo estimado**: 3-4 horas

### Archivos a crear

| Archivo | Responsabilidad |
|---|---|
| `telegram_client.py` | Envío de mensajes via python-telegram-bot |
| `telegram_webhook.py` | Endpoint POST /webhook (formato Telegram) |

### Archivos a modificar

| Archivo | Cambio |
|---|---|
| `config.py` | Agregar `TELEGRAM_ENABLED`, `TELEGRAM_WEBHOOK_SECRET` |
| `zavu_handlers.py` | Cambiar firmas: `(event: dict)` → `(chat_id: str, text: str)` |
| `zavu_webhook.py` | Extraer chat_id/text antes de llamar handlers |
| `zavu_state.py` | Persistir `_states` a SQLite |
| `services/database.py` | Agregar tabla `conversation_state` |
| `requirements.txt` | Agregar `python-telegram-bot[webhooks]` |

### Funciones nuevas

```python
# telegram_client.py
async def send_text(chat_id: int, text: str) -> None
async def send_photo(chat_id: int, photo, caption: str = "") -> None
async def send_photo_with_buttons(chat_id: int, photo, caption: str, buttons: list) -> None
async def answer_callback(callback_query_id: str, text: str = "") -> None

# telegram_webhook.py
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> JSONResponse
```

### Funciones a eliminar

Ninguna en esta fase. Zavu sigue funcionando.

### Pruebas

- [ ] Tests existentes siguen pasando (98/98)
- [ ] `send_text` envía mensaje real a Telegram
- [ ] Webhook recibe update de prueba
- [ ] FSM se persiste y recupera de SQLite

### Rollback

- Deshabilitar `TELEGRAM_ENABLED=false`
- Eliminar archivos nuevos

---

## Fase B — Webhook Telegram Live

**Objetivo**: Telegram recibe mensajes directamente. Zavu sigue activo como fallback.

**Tiempo estimado**: 2 horas

### Archivos a crear

Ninguno. Se reutiliza `telegram_webhook.py` de la Fase A.

### Archivos a modificar

| Archivo | Cambio |
|---|---|
| `telegram_webhook.py` | Montar en FastAPI app junto a `/webhook` (Zavu) |
| `Dockerfile` | CMD apunta a nuevo módulo |

### Funciones nuevas

```python
# En telegram_webhook.py o app principal
@app.on_event("startup")
async def configure_telegram_webhook():
    if Config.TELEGRAM_ENABLED:
        await bot.set_webhook(url=f"{Config.PUBLIC_BASE_URL}/webhook/telegram")
```

### Endpoints

| Método | URL | Propósito | Consumidor |
|---|---|---|---|
| `POST` | `/webhook` | Zavu (sigue activo) | Zavu |
| `POST` | `/webhook/telegram` | Telegram directo | Telegram Bot API |
| `GET` | `/health` | Healthcheck | Railway |

### Pruebas

- [ ] setWebhook retorna OK
- [ ] Mensaje /start llega por Telegram webhook
- [ ] Mensaje llega por Zavu webhook (ambos activos)
- [ ] No hay mensajes duplicados (dedup por chat_id + texto)

### Rollback

- `TELEGRAM_ENABLED=false` en Railway env vars
- Telegram webhook se desactiva en startup
- Zavu sigue funcionando

---

## Fase C — Migración de Handlers

**Objetivo**: Migrar cada handler para usar python-telegram-bot. Un handler a la vez.

**Tiempo estimado**: 4-6 horas

### Orden de migración

| # | Handler | Dificultad | Notas |
|---|---|---|---|
| 1 | `handle_start` | Baja | Solo envía menú |
| 2 | `handle_ayuda` | Baja | Solo envía texto |
| 3 | `handle_info` | Baja | Solo envía texto |
| 4 | `handle_emergencia` | Baja | Texto + API externa |
| 5 | `handle_buscar` | Media | Texto + PeopleSearch |
| 6 | `handle_free_text` | Media | Búsqueda o estado |
| 7 | `handle_registrar_cmd` | Media | Inicia FSM |
| 8 | `handle_reportar_text` | Media | Continúa FSM |
| 9 | `handle_refugios` | Media | Texto + AcopioVE |
| 10 | `handle_photo` | Alta | **Fotos funcionan** |

### Patrón de migración por handler

```python
# ANTES (Zavu)
async def handle_start(event: dict) -> None:
    chat_id = get_chat_id(event)
    clear_search_state(chat_id)
    await send_text_async(chat_id, MENU_TEXT)

# DESPUÉS (Telegram)
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    clear_search_state(str(chat_id))
    await context.bot.send_message(chat_id=chat_id, text=MENU_TEXT)
```

### Para cada handler

1. Crear versión Telegram del handler
2. Agregar a `HANDLER_MAP` de Telegram
3. Probar contra Telegram webhook
4. Verificar que Zavu handler sigue funcionando
5. Cuando esté estable, eliminar versión Zavu

### Pruebas por handler

- [ ] Comando funciona via Telegram
- [ ] Respuesta correcta
- [ ] Estados se actualizan correctamente
- [ ] No hay regresión en Zavu

### Rollback

- Cada handler migrado se puede revertir individualmente
- Feature flag por handler opcional

---

## Fase D — Limpieza

**Objetivo**: Eliminar código Zavu y configurar producción.

**Tiempo estimado**: 1 hora

### Archivos a eliminar

| Archivo | Razón |
|---|---|
| `zavu_webhook.py` | Reemplazado por `telegram_webhook.py` |
| `zavu_router.py` | Reemplazado por `telegram_router.py` |
| `zavu_handlers.py` | Reemplazado por `telegram_handlers.py` |
| `zavu_client.py` | Reemplazado por `telegram_client.py` |
| `tests/test_zavu_webhook.py` | Tests de Zavu |
| `tests/test_zavu.py` | Tests de router Zavu |
| `tests/test_zavu_handlers.py` | Tests de handlers Zavu |
| `tests/test_zavu_search_handler.py` | Tests de búsqueda Zavu |

### Archivos a modificar

| Archivo | Cambio |
|---|---|
| `requirements.txt` | Eliminar `zavudev>=0.24` |
| `config.py` | Eliminar `ZAVU_API_KEY`, `ZAVU_SENDER_ID`, `ZAVU_WEBHOOK_SECRET` |
| `.env.example` | Eliminar vars Zavu |
| `Dockerfile` | Verificar CMD |
| `README.md` | Actualizar stack, arquitectura, flujo |

### Variables de entorno a eliminar

```
ZAVU_API_KEY
ZAVU_SENDER_ID
ZAVU_WEBHOOK_SECRET
```

### Variables de entorno a mantener

```
TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_SECRET
TELEGRAM_ENABLED=true
PUBLIC_BASE_URL
PORT=8443
FOUND_PEOPLE_API_URL
DATA_DIR=./data
FACE_MATCH_THRESHOLD=0.40
FACE_MATCH_ENABLED=true
LOG_LEVEL=INFO
```

### Pruebas

- [ ] 98+ tests pasando
- [ ] Bot funciona en producción via Telegram
- [ ] No hay referencias a Zavu en el código
- [ ] Healthcheck funciona

### Rollback

- Restaurar archivos eliminados de git
- Revertir requirements.txt
- Redeploy

---

## Checklist Completo

```
☐ PREREQUISITOS
  ☐ Validar TELEGRAM_BOT_TOKEN con getMe
  ☐ Configurar PUBLIC_BASE_URL en Railway
  ☐ Agregar TELEGRAM_ENABLED a config
  ☐ Persistir FSM a SQLite
  ☐ Agregar tabla conversation_state

☐ FASE A — FUNDACIÓN
  ☐ Crear telegram_client.py
  ☐ Crear telegram_webhook.py
  ☐ Agregar python-telegram-bot a requirements.txt
  ☐ Cambiar firmas de handlers
  ☐ Actualizar zavu_webhook.py para extraer chat_id
  ☐ Tests pasan (98/98)

☐ FASE B — WEBHOOK TELEGRAM LIVE
  ☐ Montar /webhook/telegram en FastAPI
  ☐ Configurar setWebhook en startup
  ☐ Feature flag TELEGRAM_ENABLED
  ☐ Verificar mensajes llegan por Telegram
  ☐ Verificar Zavu sigue funcionando

☐ FASE C — MIGRACIÓN DE HANDLERS
  ☐ Migrar handle_start
  ☐ Migrar handle_ayuda
  ☐ Migrar handle_info
  ☐ Migrar handle_emergencia
  ☐ Migrar handle_buscar
  ☐ Migrar handle_free_text
  ☐ Migrar handle_registrar_cmd
  ☐ Migrar handle_reportar_text
  ☐ Migrar handle_refugios
  ☐ Migrar handle_photo (fotos funcionan)
  ☐ Cada handler probado individualmente

☐ FASE D — LIMPIEZA
  ☐ Eliminar zavu_webhook.py
  ☐ Eliminar zavu_router.py
  ☐ Eliminar zavu_handlers.py
  ☐ Eliminar zavu_client.py
  ☐ Eliminar tests de Zavu
  ☐ Eliminar zavudev de requirements.txt
  ☐ Eliminar vars ZAVU_* de config
  ☐ Actualizar .env.example
  ☐ Actualizar README.md
  ☐ Verificar 98+ tests pasando
  ☐ Deploy a producción
  ☐ Monitorear 24-48h
```

---

## Riesgos

| Nivel | Riesgo | Mitigación |
|---|---|---|
| Crítico | Bot caído durante migración | Feature flag + Zavu como fallback |
| Crítico | Perder mensajes de usuarios | Testear en grupo privado primero |
| Alto | Webhook no se registra | Verificar `PUBLIC_BASE_URL` primero |
| Alto | Token inválido | Validar con `getMe` antes de empezar |
| Alto | Fotos siguen sin funcionar | Con python-telegram-bot, file_id es nativo |
| Alto | Estado FSM se pierde | Persistir a SQLite antes de migrar |
| Medio | Mensajes duplicados | Dedup por chat_id + texto |
| Medio | Tests rompen | Ejecutar después de cada fase |
| Bajo | Regresión funcional | Mantener Zavu hasta verificación completa |

---

## Estimación

| Fase | Tiempo | Sesiones |
|---|---|---|
| Prerequisitos | 1h | 0.5 |
| A — Fundación | 3-4h | 1 |
| B — Webhook live | 2h | 0.5 |
| C — Handlers | 4-6h | 1.5 |
| D — Limpieza | 1h | 0.5 |
| **Total** | **~12h** | **4 sesiones** |

---

## Rollback General

Si falla cualquier fase:

1. `TELEGRAM_ENABLED=false` en Railway (instantáneo)
2. Zavu sigue activo
3. Verificar funcionamiento
4. Analizar errores antes de continuar

---

## Mejoras Futuras (fuera de este plan)

- PostgreSQL para persistencia
- Redis para estados en memoria
- GitHub Actions para CI/CD
- Rate limiting en webhook
- Sentry para monitoreo de errores
- Logging estructurado (structlog)
- Botones inline nativos (después de migración estable)
