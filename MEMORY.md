# BuscaChat Telegram — Memoria del proyecto

Para futuras sesiones: leer este archivo antes de modificar código.

---

## Identidad

- **Bot:** @BuscaChatVzla_bot — reunificación familiar post-terremoto Venezuela
- **Desastre:** Terremotos Mw 7.2 + 7.5, 24 junio 2026, epicentro Yaracuy
- **Hackathon:** Build 4 Venezuela
- **Railway:** https://buscachat-telegram-production.up.railway.app
- **Webhook:** `POST /webhook/telegram`
- **Health:** `GET /health`
- **Token:** `{{TELEGRAM_BOT_TOKEN}}` (NO hardcodear — leer de variable de entorno). Rotado en BotFather el 2026-06-30.
- **Project ID:** `celebrated-nature / Buscachat-Telegram`

## Stack

| Componente | Versión/Detalle |
|------------|-----------------|
| Python | 3.14.5 local / 3.11 Dockerfile (Railway) |
| Framework | FastAPI + uvicorn |
| Bot SDK | python-telegram-bot 22.8 (webhooks) |
| HTTP | httpx 0.28.1 (incluido por PTB), aiohttp |
| DB | SQLite (MVP), tabla: personas, embeddings, conversation_state |
| Face | ArcFace (facerec.py de Venezuela Juntos / InsightFace) |
| Hosting | Railway (Dockerfile → `uvicorn zavu_webhook:app --host 0.0.0.0 --port 8080`) |
| Tests | pytest 9.0 + pytest-asyncio (asyncio_mode=STRICT) — 132 tests |

## Dependencias clave

```
python-telegram-bot[webhooks]>=22.0
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
aiohttp>=3.11.0
httpx>=0.28.0
insightface>=0.7.3  # solo en Dockerfile
cachetools>=5.5.0
pytest-asyncio>=0.25.0
```

## Decisiones de arquitectura

- **NO usar Zavu** — eliminado. Telegram directo via python-telegram-bot
- **FSM propia** en `zavu_state.py` — NO usar `ConversationHandler` de PTB. La FSM tiene 5 pasos (NOMBRE→CEDULA→UBICACION→FOTO→CONFIRMAR) y persiste a SQLite vía `_persist()`/`_load()` con un dict en memoria (`cls._states`) como caché primaria
- **Patrón:** webhook → router (`_route_telegram`/`get_route`) → `HANDLER_MAP` → handler → telegram response
- **Singleton Bot:** `get_bot()` en `telegram_client.py`. Nunca crear instancias adicionales. Thread-safe por GIL pero `_bot` global sin lock — riesgo bajo en single-instance async
- **Wrappers async:** `send_text_async()`, `send_image_async()`, etc. usan `get_bot()` + `await` DIRECTAMENTE en el event loop de uvicorn. **NUNCA usar `asyncio.to_thread` ni `asyncio.run()`** en estos wrappers — corrompe el event loop compartido con `httpx.AsyncClient`
- **`answer_callback_async()`** también usa `await` directo desde el webhook — no bloquear el event loop con llamadas sync
- **Ruteo en webhook:** Prioridad: (1) callbacks btn:, (2) FSM activo, (3) foto sin FSM, (4) texto libre/comandos
- **Photo routing en FSM:** verificar `active_route == "photo:report"` ANTES de cualquier chequeo genérico de `message.get("photo")`

## Bugs críticos corregidos — NO VOLVER A COMETER

### 🔴 Event loop cerrado (fix: 2026-06-30, commit `9fe07ad`)

- **Síntoma:** cada 2 mensajes fallaban sin respuesta, fotos no descargaban, botones no respondían
- **Causa raíz:** `asyncio.to_thread(send_text, ...)` → `send_text()` → `ThreadPoolExecutor` → `asyncio.run(_send())`. Cada `asyncio.run()` crea y CIERRA un event loop. El `httpx.AsyncClient` interno del Bot quedaba en estado inválido.
- **Fix:** Los 6 wrappers async (`send_text_async`, `send_image_async`, `send_menu_with_buttons_async`, `edit_menu_async`, `edit_markup_async`, `answer_callback_async`) ahora llaman `get_bot().metodo()` directamente con `await` en el event loop de uvicorn. Sin thread pools, sin `asyncio.run()`.
- **Regla:** Si estás en un `async` handler con event loop corriendo, usa `await bot.metodo()` directamente. No delegates a funciones sync que manejan su propio event loop.

### 🔴 File_id filtrado como texto (fix: 2026-06-30, commit `ff9d010`)

- **Síntoma:** foto enviada en paso NOMBRE/CEDULA/UBICACION se guardaba como nombre/cédula/ubicación en la DB
- **Causa:** webhook línea 98-99 seteaba `text = message["photo"][-1]["file_id"]` para TODAS las fotos, incluso cuando el FSM no estaba en paso FOTO. Luego `handle_reportar_text` trataba ese file_id como input textual válido del usuario.
- **Fix:** Solo reemplazar `text` con `file_id` si `get_route() == "photo:report"`. Si no, dejar `text = ""`.
- **Regla:** Solo convertir photo→text cuando el FSM esté explícitamente esperando foto (step == FOTO).

### 🟠 Markdown injection (fix: 2026-06-30, commit `ff9d010`)

- **Síntoma:** nombres con `*`, `_`, `` ` `` rompían `ParseMode.MARKDOWN` → mensaje no se entregaba (Telegram devuelve 400). Usuario veía silencio y reenviaba.
- **Causa:** `_step_nombre()` usaba `f"Nombre: *{text}*\n\n..."` sin escapar el input del usuario. `_build_summary()` y `_save_report()` tenían el mismo problema.
- **Fix:** función `_escape_md()` que escapa `\`, `_`, `*`, `` ` ``. Usada en `_step_nombre`, `_build_summary`, `_save_report`.
- **Regla:** Todo input de usuario dentro de formato Markdown (`*...*`, `_..._`, `` `...` ``) debe escaparse.

### 🔴 Orden de condiciones en webhook (fix: 2026-06-30, commit `cd1a5e6`)

- **Síntoma:** subir foto en paso FOTO mostraba "No esperaba una foto ahora" en vez de procesarla
- **Causa:** `elif message.get("photo"):` atrapaba TODAS las fotos antes de que el ruteo específico `photo:report` tuviera oportunidad de ejecutarse
- **Fix:** Agregar `elif active_route == "photo:report": handler = HANDLER_MAP.get("photo:report")` ANTES del `elif message.get("photo")` genérico.
- **Regla:** El orden correcto es: (1) texto en FOTO, (2) foto en FOTO, (3) foto en otros pasos, (4) texto normal.

### 🟠 registrar_waiting consumido antes de validar (fix: 2026-06-30, commit `ff9d010`)

- **Síntoma:** usuario escribía texto cuando `_registrar_waiting` estaba activo pero el texto no era "desaparecido"/"encontrado" → caía a búsqueda en vez de recibir instrucciones
- **Causa:** `_registrar_waiting.pop()` consumía el flag incondicionalmente antes de verificar el contenido del texto
- **Fix:** Usar `_registrar_waiting.get()` para inspeccionar, `pop()` solo en match. Si no hay match, mostrar mensaje instructivo y restaurar flag.
- **Regla:** No consumir flags de estado antes de validar la entrada.

### 🟡 send_text_async no importado en webhook (fix: 2026-06-30, commit `8468f83`)

- **Síntoma:** `NameError: name 'send_text_async' is not defined` al mostrar "No esperaba una foto ahora"
- **Causa:** el `elif message.get("photo")` usaba `send_text_async` pero no estaba importado en `zavu_webhook.py`
- **Fix:** agregar `send_text_async` al import de `zavu_handlers`

## Archivos clave

| Archivo | Propósito |
|---------|-----------|
| `zavu_webhook.py` | FastAPI app, `/webhook/telegram`, `/health`, routing de updates, verificación HMAC, startup setWebhook |
| `zavu_handlers.py` | ~30 handlers (start, buscar, registrar, refugios, emergencia, ayuda, botones), `HANDLER_MAP`, async wrappers (`send_text_async`, etc.) |
| `zavu_state.py` | `ReportStateMachine`: FSM 5 pasos (NOMBRE→CEDULA→UBICACION→FOTO→CONFIRMAR), persistencia SQLite, métodos `_step_*`, `save_photo` |
| `telegram_client.py` | `get_bot()` singleton, `send_text`, `send_photo`, `send_image`, `send_menu_with_buttons`, `edit_message_text`, `edit_message_reply_markup` (sync wrappers que manejan su propio event loop) |
| `config.py` | `Config` dataclass con settings validados de env vars |
| `services/database.py` | SQLite: guardar/buscar personas, embeddings, conversation_state |
| `services/people_search.py` | `PeopleSearchAggregator`: 4 fuentes paralelas, normalización, dedup, `formatear_resultado` |
| `services/face_matching.py` | Wrapper para `lib/facerec.py` (ArcFace): `extract_embedding`, `store_embedding`, `search_similar` |
| `services/acopiove_api.py` | Cliente AcopioVE: personas, refugios, teléfonos |
| `services/found_people_api.py` | Cliente found-people-ve-bot |
| `services/reportavnzla_api.py` | Cliente ReportaVNZLA |
| `services/normalizer.py` | Normalización de texto |
| `models/persona.py` | `Persona` dataclass, `TipoReporte` enum |

## Tests

- **132/132 tests pasando** (comando: `python -m pytest tests/ -v`)
- Framework: pytest + pytest-asyncio
- Modo asyncio: `STRICT`, `asyncio_default_test_loop_scope=function`
- NO usar `monkeypatch.setattr("zavu_handlers.send_text", ...)` — `send_text` ya no existe en `zavu_handlers`
- Usar `monkeypatch.setattr("zavu_handlers.send_text_async", AsyncMock())` para silenciar envíos
- Usar `async def fake_send(chat_id, text): sent.append(text)` para capturar mensajes
- `reset_state` fixture debe limpiar `_registrar_waiting` y `_refugios_waiting` además de `ReportStateMachine._states`
- Archivos de test: `test_zavu_handlers.py`, `test_zavu_state.py` (25 tests FSM), `test_zavu_search_handler.py`, `test_fase_a.py`, `test_inline_buttons.py` (36 tests), `test_people_search.py`, `test_database.py`, `test_found_people_api.py`, `test_acopiove.py`, `test_reportavnzla.py`, `test_face_matching.py`

## Flujo de registro completo

```
Usuario → Botón "Desaparecido"
  ↓
handle_btn_registrar_desaparecido()
  → ReportStateMachine.start(chat_id, "desaparecido")
  → Crea state: {step: NOMBRE, tipo, nombre, cedula, ubicacion, foto_path, foto_file_id}
  → _persist() a SQLite
  → send_text_async(prompt: "Cual es el nombre completo?")
  ↓
Usuario escribe texto
  ↓
webhook → get_route() = "reportar:step:text" → handle_reportar_text()
  → ReportStateMachine.handle_text(chat_id, text)
    → _step_nombre(state, text): valida, state.nombre=text, step=CEDULA, _persist()
    → _step_cedula(state, text): valida dígitos o /skip, step=UBICACION, _persist()
    → _step_ubicacion(state, text): acepta cualquier texto o /skip, step=FOTO, _persist()
    → _step_foto(state, text): solo /skip → step=CONFIRMAR. Otro texto → error.
  → send_text_async(response)
  ↓
Usuario envía foto
  ↓
webhook → get_route() = "photo:report"
  → text = message["photo"][-1]["file_id"]
  → active_route = "photo:report"
  → handler = HANDLER_MAP.get("photo:report") = handle_photo_report
  → handle_photo_report(chat_id, file_id)
    → bot.get_file(file_id) → file.file_path
    → httpx.AsyncClient(timeout=30).get(file.file_path) → file_bytes
    → guarda en Config.FOTOS_DIR / f"{chat_id}_{timestamp}.jpg"
    → ReportStateMachine.save_photo(chat_id, path, file_id)
      → state.foto_path = path, state.foto_file_id = file_id, step = CONFIRMAR, _persist()
      → retorna _build_summary(state)
    → send_text_async(summary)
    → send_image_async(chat_id, file_id)  # muestra la foto al usuario
    → try: FaceMatcher.extract_embedding(file_bytes)  # embedding descartado actualmente
  ↓
Usuario escribe "Confirmar"
  ↓
handle_reportar_text("Confirmar")
  → _step_confirmar(chat_id, state, "Confirmar")
  → _save_report(chat_id, state)
    → Persona(nombre, cedula, ubicacion, foto_path, foto_file_id, tipo, reporter_chat_id)
    → db.guardar_persona(persona) → persona_id
    → cancel()  # limpia estado
    → "Reporte guardado correctamente. ID: #{persona_id}"
```

## Rutas de webhook (orden de prioridad)

```
1. callback_query AND text.startswith("btn:")
   → HANDLER_MAP.get(text) directo con message_id
   → answer_callback_async() después

2. active_route = ReportStateMachine.get_route(chat_id)
   a. "photo:report" AND NO photo → reportar:step:text  (texto en FOTO: /skip)
   b. "photo:report" → photo:report  (foto en FOTO)
   c. message.get("photo") → "No esperaba una foto ahora"  (foto en paso incorrecto)
   d. cualquier otro → HANDLER_MAP.get(active_route)

3. NO active_route AND message.get("photo")
   → HANDLER_MAP.get("photo") = handle_photo ("búsqueda por foto no disponible")

4. NO active_route AND texto
   → _route_telegram(text) OR get_search_results_route(chat_id, text)
```

## Variables de entorno (Railway)

| Variable | Valor en Railway |
|----------|-----------------|
| `TELEGRAM_ENABLED` | `true` |
| `TELEGRAM_BOT_TOKEN` | `{{TELEGRAM_BOT_TOKEN}}` (definir en Railway, nunca hardcodear) |
| `TELEGRAM_WEBHOOK_SECRET` | (configurado) |
| `PUBLIC_BASE_URL` | `https://buscachat-telegram-production.up.railway.app` |
| `FOUND_PEOPLE_API_URL` | `https://bot-production-ed0b.up.railway.app` |
| `FACE_MATCH_ENABLED` | `true` |
| `FACE_MATCH_THRESHOLD` | `0.40` |

## Comandos Railway

```bash
railway up --detach          # redeploy
railway logs --deployment    # ver logs del último deploy
railway logs                 # ver logs en tiempo real
```

## Seguridad — Reglas estrictas

- **NUNCA** hardcodear el token del bot en archivos. Usar `{{TELEGRAM_BOT_TOKEN}}` como placeholder en docs.
- **NUNCA** commitear `.env` con tokens reales. Verificar `.gitignore`.
- **Token actual expuesto** en git history (MEMORY.md, AGENTS.md, commits anteriores). **Rotar en BotFather inmediatamente.**
- `Config.validate()` rechaza `TELEGRAM_WEBHOOK_SECRET="change-me"` cuando `TELEGRAM_ENABLED=true`.
- `_verify_telegram_secret()` loggea ERROR si el secret es "change-me".
- HMAC: usar `hmac.compare_digest` (protegido contra timing attacks).

## Seguridad — Fase 2 implementada (2026-06-30)

- **Rate limiting:** 30 requests/minuto por chat_id via `TTLCache`. Si excede, retorna 429.
- **Límite de caracteres:** nombre ≤ 200, ubicación ≤ 300. Mensaje de error claro si excede.
- **Validación MIME en fotos:** solo `image/jpeg`, `image/png`, `image/webp`. Máximo 10MB. Rechaza con error si no coincide.
- **Markdown en APIs externas:** `formatear_resultado()` en `people_search.py` escapa todos los campos con `escape_md()`. `_format_search_page()` escapa `query`.
- **Pinning de dependencias:** `requirements.txt` usa `==` con versiones probadas, no `>=`.
- **`escape_md` movido a `services/normalizer.py`:** usado por `zavu_state.py`, `people_search.py`, `zavu_handlers.py`. No duplicar.

## Pendiente

- ~~Reconocimiento facial~~ → embedding extraído pero **no almacenado** en DB. Falta pasar `persona_id` a `FaceMatcher.store_embedding()`
- Búsqueda por foto funcional (FR-API ReportaVNZLA, requiere API key)
- Migración SQLite → PostgreSQL (proyecto separado)
- Almacenamiento persistente de fotos (S3/Railway Volume)
