# Fase A — Fundación: Implementación Detallada

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear infraestructura Telegram y desacoplar handlers del formato Zavu, permitiendo que los mismos handlers sean llamados desde ambos webhooks.

**Architecture:** Los handlers en `zavu_handlers.py` cambian firma de `(event: dict)` a `(chat_id: str, text: str)`. Tanto `zavu_webhook.py` (Zavu) como `telegram_webhook.py` (Telegram) extraen chat_id/text de su formato nativo y llaman los mismos handlers. Se agrega feature flag `TELEGRAM_ENABLED` para rollback instantáneo.

**Tech Stack:** python-telegram-bot[webhooks], FastAPI, SQLite, TTLCache

---

## Archivos involucrados

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `telegram_client.py` | **Crear** | Wrapper síncrono sobre python-telegram-bot para envío de mensajes |
| `telegram_webhook.py` | **Crear** | Endpoint POST `/webhook/telegram` que parsea Update de Telegram |
| `config.py` | **Modificar** | Agregar `TELEGRAM_ENABLED` |
| `zavu_handlers.py` | **Modificar** | Cambiar firmas de todos los handlers |
| `zavu_webhook.py` | **Modificar** | Extraer chat_id/text de evento Zavu antes de llamar handlers |
| `zavu_state.py` | **Modificar** | Persistir `_states` a SQLite via database.py |
| `services/database.py` | **Modificar** | Agregar tabla `conversation_state` + CRUD |
| `requirements.txt` | **Modificar** | Agregar `python-telegram-bot[webhooks]>=22.0` |
| `tests/test_fase_a.py` | **Crear** | Tests para telegram_client, telegram_webhook, state persistence |

---

## Task 1: Agregar dependencia

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Agregar python-telegram-bot**

Agregar al final de `requirements.txt`:

```
python-telegram-bot[webhooks]>=22.0
```

- [ ] **Step 2: Instalar localmente**

Run: `pip install -r requirements.txt`

- [ ] **Step 3: Verificar importación**

Run: `python -c "import telegram; print(telegram.__version__)"`

Expected: Versión >= 22.0

---

## Task 2: Config — feature flag TELEGRAM_ENABLED

**Files:**
- Modify: `config.py:9-12`

- [ ] **Step 1: Agregar TELEGRAM_ENABLED a Config**

En `config.py`, después de la línea 11 (`TELEGRAM_WEBHOOK_SECRET`), agregar:

```python
TELEGRAM_ENABLED: bool = os.environ.get("TELEGRAM_ENABLED", "false").lower() == "true"
```

La clase Config queda así (líneas relevantes):

```python
class Config:
    TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_SECRET: str = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "change-me")
    TELEGRAM_ENABLED: bool = os.environ.get("TELEGRAM_ENABLED", "false").lower() == "true"
    PUBLIC_BASE_URL: str = os.environ.get("PUBLIC_BASE_URL", "")
    # ... resto igual
```

- [ ] **Step 2: Verificar que tests existentes pasan**

Run: `pytest tests/ -v`

Expected: 98/98 pasan (el flag default es `false`, no afecta nada)

---

## Task 3: Telegram client — wrapper de envío

**Files:**
- Create: `telegram_client.py`

- [ ] **Step 1: Crear telegram_client.py**

```python
import logging
from telegram import Bot
from telegram.constants import ParseMode

from config import Config

logger = logging.getLogger(__name__)

_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
    return _bot


def send_text(chat_id: int, text: str) -> None:
    import asyncio

    async def _send():
        bot = get_bot()
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(f"Message sent to {chat_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())


def send_photo(chat_id: int, photo: str, caption: str = "") -> None:
    import asyncio

    async def _send():
        bot = get_bot()
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(f"Photo sent to {chat_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())


def answer_callback(callback_query_id: str, text: str = "") -> None:
    import asyncio

    async def _send():
        bot = get_bot()
        await bot.answer_callback_query(
            callback_query_id=callback_query_id,
            text=text,
        )
        logger.info(f"Callback answered: {callback_query_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())
```

- [ ] **Step 2: Verificar que el módulo importa sin errores**

Run: `python -c "from telegram_client import send_text, send_photo, answer_callback; print('OK')"`

Expected: `OK`

---

## Task 4: Database — tabla conversation_state

**Files:**
- Modify: `services/database.py:21-51`

- [ ] **Step 1: Agregar tabla conversation_state en _init_db**

En `services/database.py`, método `_init_db`, después del `CREATE TABLE IF NOT EXISTS embeddings` (línea 46), antes del `conn.commit()` (línea 51), agregar:

```python
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_state (
                    chat_id TEXT PRIMARY KEY,
                    state_data TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
```

- [ ] **Step 2: Agregar métodos CRUD para conversation_state**

Al final de la clase `Database` (antes de `_db_instance`, línea 212), agregar:

```python
    def save_conversation_state(self, chat_id: str, state_data: str) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO conversation_state
                       (chat_id, state_data, updated_at)
                       VALUES (?, ?, ?)""",
                    (chat_id, state_data, datetime.now(UTC).isoformat()),
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error saving conversation state: {e}")

    def load_conversation_state(self, chat_id: str) -> Optional[str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT state_data FROM conversation_state WHERE chat_id = ?",
                    (chat_id,),
                ).fetchone()
                return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Database error loading conversation state: {e}")
            return None

    def delete_conversation_state(self, chat_id: str) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM conversation_state WHERE chat_id = ?",
                    (chat_id,),
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error deleting conversation state: {e}")
```

- [ ] **Step 3: Verificar que la tabla se crea**

Run: `python -c "from services.database import get_db; db = get_db(); print('table created OK')"`

Expected: `OK`

---

## Task 5: State — persistir FSM a SQLite

**Files:**
- Modify: `zavu_state.py`

- [ ] **Step 1: Modificar ReportStateMachine para persistir**

Reemplazar el contenido completo de `zavu_state.py`:

```python
import json
import logging
from typing import Optional

from models.persona import Persona, TipoReporte
from services.database import get_db

logger = logging.getLogger(__name__)

db = get_db()

NOMBRE = "reportar:step:nombre"
CEDULA = "reportar:step:cedula"
UBICACION = "reportar:step:ubicacion"
CONFIRMAR = "reportar:step:confirmar"


class ReportStateMachine:
    _states: dict[str, dict] = {}

    @classmethod
    def _persist(cls, chat_id: str) -> None:
        state = cls._states.get(chat_id)
        if state:
            db.save_conversation_state(chat_id, json.dumps(state))
        else:
            db.delete_conversation_state(chat_id)

    @classmethod
    def _load(cls, chat_id: str) -> Optional[dict]:
        if chat_id in cls._states:
            return cls._states[chat_id]
        data = db.load_conversation_state(chat_id)
        if data:
            cls._states[chat_id] = json.loads(data)
            return cls._states[chat_id]
        return None

    @classmethod
    def is_active(cls, chat_id: str) -> bool:
        return cls._load(chat_id) is not None

    @classmethod
    def get_route(cls, chat_id: str) -> Optional[str]:
        state = cls._load(chat_id)
        if not state:
            return None
        return "reportar:step:text"

    @classmethod
    def start(cls, chat_id: str, tipo: str) -> str:
        logger.info(f"Reportar start: tipo={tipo} chat_id={chat_id}")
        cls._states[chat_id] = {
            "step": NOMBRE,
            "tipo": tipo,
            "nombre": None,
            "cedula": None,
            "ubicacion": None,
            "foto_path": None,
            "foto_file_id": None,
        }
        cls._persist(chat_id)
        tipo_text = "desaparecido/a" if tipo == "desaparecido" else "encontrado/a"
        return f"*Reportar persona {tipo_text}*\n\nCual es el nombre completo de la persona?"

    @classmethod
    def handle_text(cls, chat_id: str, text: str) -> Optional[str]:
        state = cls._load(chat_id)
        if not state:
            return None

        step = state["step"]
        text = text.strip()

        # Universal escapes — work at ANY step
        if text in ("/cancel", "Cancelar", "/start"):
            cls.cancel(chat_id)
            return None

        if step == NOMBRE:
            result = cls._step_nombre(state, text)
        elif step == CEDULA:
            result = cls._step_cedula(state, text)
        elif step == UBICACION:
            result = cls._step_ubicacion(state, text)
        elif step == CONFIRMAR:
            result = cls._step_confirmar(chat_id, state, text)
        else:
            result = None

        if result is not None and chat_id in cls._states:
            cls._persist(chat_id)

        return result

    @classmethod
    def _step_nombre(cls, state: dict, text: str) -> Optional[str]:
        if len(text) < 2:
            return "El nombre debe tener al menos 2 caracteres. Proba de nuevo:"
        state["nombre"] = text
        state["step"] = CEDULA
        return f"Nombre: *{text}*\n\nCual es el numero de cedula?\nEscribi /skip si no sabes."

    @classmethod
    def _step_cedula(cls, state: dict, text: str) -> Optional[str]:
        if text == "/skip":
            state["cedula"] = ""
        elif not text.isdigit():
            return "La cedula debe contener solo numeros. Proba de nuevo o escribi /skip:"
        else:
            state["cedula"] = text
        state["step"] = UBICACION
        return "En que ubicacion fue vista por ultima vez?\nEscribi /skip si no sabes."

    @classmethod
    def _step_ubicacion(cls, state: dict, text: str) -> Optional[str]:
        if text == "/skip":
            state["ubicacion"] = ""
        else:
            state["ubicacion"] = text
        state["step"] = CONFIRMAR
        return cls._build_summary(state)

    @classmethod
    def _step_confirmar(cls, chat_id: str, state: dict, text: str) -> Optional[str]:
        if text.lower() != "confirmar":
            return "Escribi *Confirmar* para guardar o *Cancelar* para descartar."

        return cls._save_report(chat_id, state)

    @classmethod
    def _save_report(cls, chat_id: str, state: dict) -> Optional[str]:
        tipo_str = state.get("tipo", "desaparecido")
        tipo = TipoReporte.DESAPARECIDO if tipo_str == "desaparecido" else TipoReporte.ENCONTRADO
        logger.info(f"Save report: tipo_str={tipo_str} tipo={tipo.value} chat_id={chat_id}")
        persona = Persona(
            nombre=state.get("nombre", ""),
            cedula=state.get("cedula", ""),
            ubicacion=state.get("ubicacion", ""),
            foto_path=state.get("foto_path"),
            foto_file_id=state.get("foto_file_id"),
            tipo=tipo,
            reporter_chat_id=int(chat_id) if chat_id.isdigit() else 0,
        )

        try:
            persona_id = db.guardar_persona(persona)
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            cls.cancel(chat_id)
            return "Error al guardar el reporte. Proba de nuevo con /start."

        tipo_text = "desaparecido/a" if persona.tipo == TipoReporte.DESAPARECIDO else "encontrado/a"
        cls.cancel(chat_id)
        return (
            f"*Reporte guardado correctamente*\n\n"
            f"ID: #{persona_id}\n"
            f"Nombre: {persona.nombre}\n"
            f"Tipo: {tipo_text}\n\n"
            "Escribi /start para volver al menu."
        )

    @classmethod
    def _build_summary(cls, state: dict) -> str:
        tipo_str = state.get("tipo", "desaparecido")
        tipo_text = "desaparecido/a" if tipo_str == "desaparecido" else "encontrado/a"
        logger.info(f"Build summary: tipo_str={tipo_str} tipo_text={tipo_text}")
        return (
            f"*Resumen del reporte*\n\n"
            f"Tipo: *{tipo_text}*\n"
            f"Nombre: *{state.get('nombre', '-')}*\n"
            f"Cedula: {state.get('cedula') or 'No informada'}\n"
            f"Ubicacion: {state.get('ubicacion') or 'No informada'}\n\n"
            "Escribi *Confirmar* para guardar o *Cancelar* para descartar."
        )

    @classmethod
    def cancel(cls, chat_id: str):
        cls._states.pop(chat_id, None)
        db.delete_conversation_state(chat_id)
        logger.info(f"Report state cancelled for chat_id={chat_id}")
```

- [ ] **Step 2: Verificar que tests existentes de state pasan**

Run: `pytest tests/test_zavu_state.py -v`

Expected: Todos pasan

---

## Task 6: Handlers — cambiar firmas

**Files:**
- Modify: `zavu_handlers.py`

- [ ] **Step 1: Cambiar firmas de todos los handlers**

En `zavu_handlers.py`, cambiar cada función de `handler(event: dict)` a `handler(chat_id: str, text: str)`.

Cambiar las siguientes funciones (reemplazar el bloque completo de cada una):

**Línea 102-106** — `handle_start`:
```python
async def handle_start(chat_id: str, text: str = "") -> None:
    ReportStateMachine.cancel(chat_id)
    clear_search_state(chat_id)
    await send_text_async(chat_id, MENU_TEXT)
```

**Línea 109-112** — `handle_menu`:
```python
async def handle_menu(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(chat_id, MENU_TEXT)
```

**Línea 115-119** — `handle_menu_registrar`:
```python
async def handle_menu_registrar(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    _registrar_waiting[chat_id] = True
    await send_text_async(chat_id, REGISTRAR_TEXT)
```

**Línea 122-125** — `handle_ayuda`:
```python
async def handle_ayuda(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(chat_id, AYUDA_TEXT)
```

**Línea 128-131** — `handle_info`:
```python
async def handle_info(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(chat_id, INFO_TEXT)
```

**Línea 134-150** — `handle_buscar`:
```python
async def handle_buscar(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    parts = text.split(maxsplit=1)
    query = parts[1] if len(parts) > 1 else ""

    if not query:
        await send_text_async(
            chat_id,
            "*Buscar persona*\n\n"
            "Escribi el nombre o cedula de la persona que buscas.\n"
            "Ejemplo: Maria Perez",
        )
        return

    await _realizar_busqueda(chat_id, query)
```

**Línea 153-159** — `handle_buscar_button`:
```python
async def handle_buscar_button(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(
        chat_id,
        "*Buscar persona*\n\nEscribi el nombre o cedula de la persona que buscas:",
    )
```

**Línea 162-186** — `handle_free_text`:
```python
async def handle_free_text(chat_id: str, text: str = "") -> None:
    query = text.strip()

    if len(query) < 2:
        await send_text_async(chat_id, "Escribi al menos 2 caracteres para buscar.")
        return

    if _refugios_waiting.pop(chat_id, None):
        await _buscar_refugios(chat_id, query)
        return

    if _registrar_waiting.pop(chat_id, None):
        if query.lower() in ("desaparecido", "encontrado"):
            tipo = query.lower()
            prompt = ReportStateMachine.start(chat_id, tipo)
            await send_text_async(chat_id, prompt)
            return
        elif query.lower() in ("desaparecida", "encontrada"):
            tipo = query.lower().rstrip("a")
            prompt = ReportStateMachine.start(chat_id, tipo)
            await send_text_async(chat_id, prompt)
            return

    await _realizar_busqueda(chat_id, query)
```

**Línea 189-196** — `handle_photo`:
```python
async def handle_photo(chat_id: str, text: str = "") -> None:
    logger.info(f"PHOTO EVENT (free search): chat_id={chat_id}")
    await send_text_async(
        chat_id,
        "La busqueda por foto no esta disponible por ahora.\n\n"
        "Usa /buscar con nombre o cedula para buscar personas.",
    )
```

**Línea 225-248** — `handle_search_more`:
```python
async def handle_search_more(chat_id: str, text: str = "") -> None:
    state = _search_results_state.get(chat_id)

    if not state:
        await send_text_async(chat_id, MENU_TEXT)
        return

    next_index = state["next_index"]
    results = state["results"]

    if next_index >= len(results):
        await send_text_async(
            chat_id,
            "*Ya mostre todos los resultados disponibles.*\n\n"
            "Escribe *2* para hacer otra busqueda o *3* para volver al menu.",
        )
        return

    response, fotos = _format_search_page(state["query"], results, next_index)
    state["next_index"] = min(next_index + SEARCH_PAGE_SIZE, len(results))
    await send_text_async(chat_id, response)
    for foto_url in fotos:
        await send_image_async(chat_id, foto_url)
```

**Línea 251-257** — `handle_search_new`:
```python
async def handle_search_new(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(
        chat_id,
        "*Buscar persona*\n\nEscribi el nombre o cedula de la persona que buscas:",
    )
```

**Línea 260-263** — `handle_search_menu`:
```python
async def handle_search_menu(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(chat_id, MENU_TEXT)
```

**Línea 293-306** — `handle_registrar_cmd`:
```python
async def handle_registrar_cmd(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    _registrar_waiting.pop(chat_id, None)

    if "encontrado" in text:
        tipo = "encontrado"
    else:
        tipo = "desaparecido"

    logger.info(f"Registrar: text={text[:50]} tipo={tipo} chat_id={chat_id}")
    prompt = ReportStateMachine.start(chat_id, tipo)
    await send_text_async(chat_id, prompt)
```

**Línea 309-324** — `handle_reportar_text`:
```python
async def handle_reportar_text(chat_id: str, text: str = "") -> None:
    text = text.strip()

    if not text:
        await send_text_async(chat_id, "Escribi una respuesta valida.")
        return

    response = ReportStateMachine.handle_text(chat_id, text)

    if response is None:
        # State was canceled (via /start, /cancel, or "Cancelar")
        await send_text_async(chat_id, MENU_TEXT)
        return

    await send_text_async(chat_id, response)
```

**Línea 327-349** — `handle_emergencia`:
```python
async def handle_emergencia(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(chat_id, "Buscando telefonos de emergencia...")

    telefonos = await acopiove.buscar_telefonos()

    if not telefonos:
        await send_text_async(
            chat_id,
            "No se encontraron telefonos de emergencia.\n\n"
            "Numeros generales:\n"
            "▸ 911 — Emergencias\n"
            "▸ 171 — Proteccion Civil\n"
            "▸ 0800 — Cruz Roja",
        )
        return

    respuesta = "📞 *Telefonos de emergencia*\n\n"
    for tel in telefonos[:8]:
        respuesta += f"{acopiove.formatear_telefono(tel)}\n\n"

    await send_text_async(chat_id, respuesta)
```

**Línea 352-370** — `handle_refugios`:
```python
async def handle_refugios(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    parts = text.split(maxsplit=1)
    ciudad = parts[1] if len(parts) > 1 else ""

    if ciudad:
        _refugios_waiting.pop(chat_id, None)
        await _buscar_refugios(chat_id, ciudad)
        return

    _refugios_waiting[chat_id] = True
    await send_text_async(
        chat_id,
        "🏠 *Refugios y centros de ayuda*\n\n"
        "Escribe el nombre de tu ciudad para buscar refugios cercanos.\n"
        "Ejemplo: Caracas, Catia La Mar, La Guaira",
    )
```

- [ ] **Step 2: Verificar que tests de handlers pasan**

Run: `pytest tests/test_zavu_handlers.py -v`

Expected: Todos pasan (tests usan `make_event` que pasa event dict; hay que actualizar los tests en Task 8)

**NOTA:** Los tests actuales en `test_zavu_handlers.py` llaman handlers con `event` dict. Después de cambiar firmas, estos tests fallarán. Se actualizan en Task 8.

---

## Task 7: Zavu webhook — extraer chat_id/text

**Files:**
- Modify: `zavu_webhook.py:85-108`

- [ ] **Step 1: Modificar el loop principal del webhook**

En `zavu_webhook.py`, reemplazar el bloque `try` (líneas 85-108) con:

```python
    try:
        chat_id = get_chat_id(event)
        data = event.get("data", {})
        text = data.get("text", "").strip()

        active_route = ReportStateMachine.get_route(chat_id)

        if active_route:
            handler = HANDLER_MAP.get("reportar:step:text")

            if handler:
                await handler(chat_id, text)
                logger.info(f"Event {event_id}: state machine step {active_route} (chat_id={chat_id})")
            else:
                logger.warning(f"No handler for state route: {active_route}")
        else:
            handler_name = get_search_results_route(chat_id, text) or route_event(event)

            if handler_name:
                handler = HANDLER_MAP.get(handler_name)
                if handler:
                    await handler(chat_id, text)
                    logger.info(f"Event {event_id} handled by {handler_name} (chat_id={chat_id})")
                else:
                    logger.warning(f"No handler for route: {handler_name}")
            else:
                logger.info(f"Event {event_id}: no route matched (chat_id={chat_id})")

    except Exception as e:
        logger.error(f"Error processing event {event_id}: {e}", exc_info=True)
```

- [ ] **Step 2: Modificar get_search_results_route**

En `zavu_handlers.py`, cambiar la función `get_search_results_route` (líneas 82-99) para que acepte `text` en vez de `event`:

```python
def get_search_results_route(chat_id: str, text: str) -> str | None:
    if chat_id not in _search_results_state:
        return None

    text = text.strip()
    if text == "1":
        return "search:more"
    if text == "2":
        return "search:new"
    if text == "3":
        return "search:menu"
    if text in ("/cancel", "Cancelar"):
        return "search:menu"
    return None
```

- [ ] **Step 3: Actualizar la llamada en zavu_webhook.py**

En `zavu_webhook.py`, línea 98, cambiar:

```python
# ANTES
handler_name = get_search_results_route(chat_id, event) or route_event(event)

# DESPUÉS
handler_name = get_search_results_route(chat_id, text) or route_event(event)
```

- [ ] **Step 4: Verificar que webhook tests pasan**

Run: `pytest tests/test_zavu_webhook.py -v`

Expected: Todos pasan

---

## Task 8: Telegram webhook — endpoint /webhook/telegram

**Files:**
- Create: `telegram_webhook.py`

- [ ] **Step 1: Crear telegram_webhook.py**

```python
import logging
import hashlib
import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BuscaChat Telegram Webhook")


@app.get("/health")
async def health():
    return {"status": "ok"}


def _verify_telegram_secret(secret_header: str) -> bool:
    if not Config.TELEGRAM_WEBHOOK_SECRET or Config.TELEGRAM_WEBHOOK_SECRET == "change-me":
        return True
    return hmac.compare_digest(secret_header, Config.TELEGRAM_WEBHOOK_SECRET)


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not _verify_telegram_secret(secret):
        logger.warning("Invalid Telegram webhook secret")
        return JSONResponse({"status": "error"}, status_code=403)

    update = await request.json()

    message = update.get("message") or update.get("callback_query")
    if not message:
        return JSONResponse({"status": "ignored"})

    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = str(cb["message"]["chat"]["id"])
        text = cb.get("data", "")
        callback_query_id = cb["id"]
    else:
        chat_id = str(message["chat"]["id"])
        text = message.get("text", "")
        callback_query_id = None

    if not text and message.get("photo"):
        text = ""

    logger.info(f"Telegram update: chat_id={chat_id} text={text[:50]}")

    from zavu_handlers import HANDLER_MAP, get_search_results_route
    from zavu_state import ReportStateMachine

    try:
        active_route = ReportStateMachine.get_route(chat_id)

        if active_route:
            handler = HANDLER_MAP.get("reportar:step:text")
            if handler:
                await handler(chat_id, text)
                logger.info(f"Telegram: state machine step for chat_id={chat_id}")
        else:
            handler_name = _route_telegram(text) or get_search_results_route(chat_id, text)

            if handler_name:
                handler = HANDLER_MAP.get(handler_name)
                if handler:
                    await handler(chat_id, text)
                    logger.info(f"Telegram: {handler_name} for chat_id={chat_id}")
                else:
                    logger.warning(f"No handler for route: {handler_name}")
            else:
                logger.info(f"Telegram: no route for chat_id={chat_id} text={text[:30]}")

        if callback_query_id:
            from telegram_client import answer_callback
            answer_callback(callback_query_id)

    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}", exc_info=True)

    return JSONResponse({"status": "ok"})


def _route_telegram(text: str) -> str | None:
    text = text.strip()

    if text.startswith("/start"):
        return "start"
    if text.startswith("/buscar"):
        return "buscar"
    if text.startswith("/ayuda"):
        return "ayuda"
    if text.startswith("/info"):
        return "info"
    if text.startswith("/registrar"):
        return "registrar_cmd"
    if text.startswith("/emergencia") or text.startswith("/telefonos"):
        return "emergencia"
    if text.startswith("/refugios") or text.startswith("/centros"):
        return "refugios"
    if text.startswith("/"):
        return None

    if text == "1":
        return "menu:buscar"
    if text == "2":
        return "menu:registrar"
    if text == "3":
        return "menu:refugios"
    if text == "4":
        return "menu:emergencia"
    if text == "5":
        return "ayuda"

    if len(text) >= 2:
        return "free_text"

    return None
```

- [ ] **Step 2: Verificar importación**

Run: `python -c "from telegram_webhook import app; print('OK')"`

Expected: `OK`

---

## Task 9: Tests — actualizar y crear nuevos

**Files:**
- Modify: `tests/test_zavu_handlers.py`
- Create: `tests/test_fase_a.py`

- [ ] **Step 1: Actualizar test_zavu_handlers.py**

Reemplazar la función `make_event` y las llamadas a handlers:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture(autouse=True)
def reset_state():
    from zavu_state import ReportStateMachine
    ReportStateMachine._states = {}
    yield


CHAT_ID = "123456"


class FakePeopleSearch:
    async def buscar(self, query):
        from services.people_search import PeopleSearchResult

        return [
            PeopleSearchResult(
                nombre="Test Person",
                fuente="ReportaVNZLA",
            )
        ]

    def formatear_resultado(self, result):
        return f"*{result.nombre}*\nFuente: {result.fuente}"


class TestZavuHandlers:
    def test_handle_start_cancels_state(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine
        ReportStateMachine.start(CHAT_ID, "desaparecido")
        assert ReportStateMachine.is_active(CHAT_ID)

        import asyncio
        from zavu_handlers import handle_start
        asyncio.run(handle_start(CHAT_ID, "/start"))
        assert not ReportStateMachine.is_active(CHAT_ID)

    def test_handle_menu_registrar_sets_waiting(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        import asyncio
        from zavu_handlers import handle_menu_registrar, _registrar_waiting

        asyncio.run(handle_menu_registrar(CHAT_ID, "2"))
        assert _registrar_waiting.get(CHAT_ID) is True

    def test_handle_refugios_sets_waiting(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        import asyncio
        from zavu_handlers import handle_refugios, _refugios_waiting

        asyncio.run(handle_refugios(CHAT_ID, "/refugios"))
        assert _refugios_waiting.get(CHAT_ID) is True

    def test_handle_refugios_with_city(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))

        async def mock_buscar_puntos(**kwargs):
            return [{"nombre": "Refugio X", "ciudad": "Caracas"}]

        monkeypatch.setattr("zavu_handlers.acopiove", MagicMock())
        from zavu_handlers import acopiove
        acopiove.buscar_puntos = mock_buscar_puntos

        import asyncio
        from zavu_handlers import handle_refugios
        asyncio.run(handle_refugios(CHAT_ID, "/refugios Caracas"))

        assert any("Caracas" in s for s in sent)

    def test_handle_free_text_short(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))

        import asyncio
        from zavu_handlers import handle_free_text
        asyncio.run(handle_free_text(CHAT_ID, "M"))

        assert any("2 caracteres" in s for s in sent)

    def test_handle_free_text_search(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        monkeypatch.setattr("zavu_handlers.people_search", FakePeopleSearch())

        import asyncio
        from zavu_handlers import handle_free_text
        asyncio.run(handle_free_text(CHAT_ID, "Test"))

        assert any("Buscando" in s for s in sent)

    def test_handle_buscar_with_query(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        monkeypatch.setattr("zavu_handlers.people_search", FakePeopleSearch())

        import asyncio
        from zavu_handlers import handle_buscar
        asyncio.run(handle_buscar(CHAT_ID, "/buscar Maria"))

        assert any("Buscando" in s for s in sent)

    def test_handle_buscar_without_query(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        import asyncio
        from zavu_handlers import handle_buscar
        asyncio.run(handle_buscar(CHAT_ID, "/buscar"))
        assert any("nombre o cedula" in s for s in sent)

    def test_handle_photo_disabled(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        import asyncio
        from zavu_handlers import handle_photo
        asyncio.run(handle_photo(CHAT_ID, ""))
        assert any("no esta disponible" in s for s in sent)

    def test_handle_info(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        import asyncio
        from zavu_handlers import handle_info
        asyncio.run(handle_info(CHAT_ID, "/info"))
        assert any("Fuentes" in s for s in sent)

    def test_handle_registrar_cmd_desaparecido(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine

        import asyncio
        from zavu_handlers import handle_registrar_cmd
        asyncio.run(handle_registrar_cmd(CHAT_ID, "/registrar desaparecido"))

        assert ReportStateMachine.is_active(CHAT_ID)

    def test_handle_registrar_cmd_encontrado(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine

        import asyncio
        from zavu_handlers import handle_registrar_cmd
        asyncio.run(handle_registrar_cmd(CHAT_ID, "/registrar encontrado"))

        assert ReportStateMachine.is_active(CHAT_ID)

    def test_handle_reportar_text_continues_flow(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine
        ReportStateMachine.start(CHAT_ID, "desaparecido")

        import asyncio
        from zavu_handlers import handle_reportar_text
        asyncio.run(handle_reportar_text(CHAT_ID, "Maria Perez"))

        assert ReportStateMachine.is_active(CHAT_ID)

    def test_handle_reportar_text_cancel(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine
        ReportStateMachine.start(CHAT_ID, "desaparecido")

        import asyncio
        from zavu_handlers import handle_reportar_text
        asyncio.run(handle_reportar_text(CHAT_ID, "/cancel"))

        assert not ReportStateMachine.is_active(CHAT_ID)
```

- [ ] **Step 2: Crear tests/test_fase_a.py**

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json


class TestTelegramClient:
    def test_import(self):
        from telegram_client import send_text, send_photo, answer_callback
        assert callable(send_text)
        assert callable(send_photo)
        assert callable(answer_callback)

    @patch("telegram_client.get_bot")
    def test_send_text_calls_bot(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        mock_get_bot.return_value = mock_bot

        import asyncio
        from telegram_client import send_text
        asyncio.run(send_text(123456, "Hello"))

        mock_bot.send_message.assert_called_once()

    @patch("telegram_client.get_bot")
    def test_send_photo_calls_bot(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.send_photo = AsyncMock()
        mock_get_bot.return_value = mock_bot

        import asyncio
        from telegram_client import send_photo
        asyncio.run(send_photo(123456, "https://example.com/photo.jpg", "caption"))

        mock_bot.send_photo.assert_called_once()


class TestConfigFlag:
    def test_telegram_enabled_default_false(self):
        from config import Config
        assert Config.TELEGRAM_ENABLED is False

    def test_telegram_enabled_can_be_true(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_ENABLED", "true")
        import importlib
        from config import Config
        importlib.reload(Config)
        assert Config.TELEGRAM_ENABLED is True
        monkeypatch.delenv("TELEGRAM_ENABLED")
        importlib.reload(Config)


class TestStatePersistence:
    def test_save_and_load(self):
        from services.database import get_db
        db = get_db()
        db.save_conversation_state("test_chat", '{"step": "test"}')
        result = db.load_conversation_state("test_chat")
        assert result == '{"step": "test"}'
        db.delete_conversation_state("test_chat")
        assert db.load_conversation_state("test_chat") is None

    def test_state_persists_across_instances(self):
        from services.database import Database
        db1 = Database()
        db1.save_conversation_state("persist_test", '{"step": "nombre"}')
        db2 = Database()
        result = db2.load_conversation_state("persist_test")
        assert result == '{"step": "nombre"}'
        db1.delete_conversation_state("persist_test")


class TestTelegramWebhook:
    def test_import(self):
        from telegram_webhook import app
        assert app is not None

    def test_health(self):
        from fastapi.testclient import TestClient
        from telegram_webhook import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_verify_telegram_secret_valid(self):
        from telegram_webhook import _verify_telegram_secret
        from config import Config
        Config.TELEGRAM_WEBHOOK_SECRET = "test_secret"
        assert _verify_telegram_secret("test_secret") is True
        assert _verify_telegram_secret("wrong") is False

    def test_verify_telegram_secret_skip(self):
        from telegram_webhook import _verify_telegram_secret
        from config import Config
        Config.TELEGRAM_WEBHOOK_SECRET = "change-me"
        assert _verify_telegram_secret("anything") is True

    def test_route_telegram_commands(self):
        from telegram_webhook import _route_telegram
        assert _route_telegram("/start") == "start"
        assert _route_telegram("/buscar Maria") == "buscar"
        assert _route_telegram("/ayuda") == "ayuda"
        assert _route_telegram("/info") == "info"
        assert _route_telegram("/registrar encontrado") == "registrar_cmd"
        assert _route_telegram("/emergencia") == "emergencia"
        assert _route_telegram("/refugios") == "refugios"
        assert _route_telegram("/unknown") is None

    def test_route_telegram_menu(self):
        from telegram_webhook import _route_telegram
        assert _route_telegram("1") == "menu:buscar"
        assert _route_telegram("2") == "menu:registrar"
        assert _route_telegram("3") == "menu:refugios"
        assert _route_telegram("4") == "menu:emergencia"
        assert _route_telegram("5") == "ayuda"

    def test_route_telegram_free_text(self):
        from telegram_webhook import _route_telegram
        assert _route_telegram("Maria Perez") == "free_text"
        assert _route_telegram("M") is None
```

- [ ] **Step 3: Ejecutar todos los tests**

Run: `pytest tests/ -v`

Expected: Todos pasan

---

## Task 10: Verificación final

- [ ] **Step 1: Ejecutar suite completa de tests**

Run: `pytest tests/ -v --tb=short`

Expected: Todos pasan (98+ tests)

- [ ] **Step 2: Verificar que el bot Zavu sigue funcionando**

Verificar que `zavu_webhook.py` sigue montando la app correctamente:

Run: `python -c "from zavu_webhook import app; print('Zavu app OK')"`

Expected: `Zavu app OK`

- [ ] **Step 3: Verificar que telegram_webhook.py funciona**

Run: `python -c "from telegram_webhook import app; print('Telegram app OK')"`

Expected: `Telegram app OK`

- [ ] **Step 4: Verificar feature flag**

Run: `python -c "from config import Config; print(f'TELEGRAM_ENABLED={Config.TELEGRAM_ENABLED}')"`

Expected: `TELEGRAM_ENABLED=False`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(fase-a): crear infraestructura Telegram y desacoplar handlers

- Crear telegram_client.py (wrapper python-telegram-bot)
- Crear telegram_webhook.py (endpoint /webhook/telegram)
- Agregar TELEGRAM_ENABLED feature flag a config.py
- Cambiar firmas de handlers: (event) -> (chat_id, text)
- Persistir FSM a SQLite via conversation_state table
- Agregar python-telegram-bot>=22.0 a requirements.txt
- Tests actualizados y nuevos tests para Fase A"
```

---

## Resumen de cambios

| Qué se hizo | Por qué |
|---|---|
| `telegram_client.py` | Wrapper para enviar mensajes via python-telegram-bot |
| `telegram_webhook.py` | Endpoint que recibe updates de Telegram y llama a los handlers |
| `config.py` | Feature flag `TELEGRAM_ENABLED` para rollback instantáneo |
| `zavu_handlers.py` | Firmas desacopladas del formato Zavu |
| `zavu_webhook.py` | Extrae chat_id/text del evento Zavu antes de llamar handlers |
| `zavu_state.py` | FSM se persiste a SQLite (sobrevive deploys) |
| `services/database.py` | Tabla `conversation_state` + CRUD |
| `requirements.txt` | `python-telegram-bot[webhooks]>=22.0` |

## Rollback

Si algo falla:
1. `TELEGRAM_ENABLED=false` (default) — Telegram webhook no se activa
2. Zavu sigue funcionando con los handlers actualizados
3. `git revert` del commit si es necesario
