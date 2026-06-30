# Inline Buttons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add inline keyboard buttons to the BuscaChat Telegram bot main menu and sub-options, replacing text-based navigation.

**Architecture:** Add 3 new functions to telegram_client.py for sending/editing messages with inline keyboards. Modify handlers to accept optional message_id for edit-in-place. Extend webhook to parse callback_query and route btn:* prefixed callbacks. Add 15 new sub-option handlers.

**Tech Stack:** python-telegram-bot[webhooks]>=22.0, FastAPI, pytest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| telegram_client.py | Modify | +3 functions: send_menu_with_buttons, edit_message_text, edit_message_reply_markup |
| zavu_handlers.py | Modify | +message_id param, +helpers, +15 sub-option handlers, +HANDLER_MAP keys |
| zavu_webhook.py | Modify | +message_id extraction, +btn:* routing |
| tests/test_inline_buttons.py | Create | All tests for inline button functionality |

---

### Task 1: Add send_menu_with_buttons to telegram_client.py

**Files:**
- Modify: telegram_client.py
- Test: tests/test_inline_buttons.py

- [ ] **Step 1: Write the failing test**

`python
# tests/test_inline_buttons.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestSendMenuWithButtons:
    @patch("telegram_client.get_bot")
    def test_send_menu_with_buttons_calls_bot(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import send_menu_with_buttons
        buttons = [[{"text": "Buscar", "callback_data": "btn:1"}]]
        send_menu_with_buttons(123456, "Menu text", buttons)

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == 123456
        assert call_kwargs["text"] == "Menu text"
        assert call_kwargs["reply_markup"] is not None
`

- [ ] **Step 2: Run test to verify it fails**

Run: pytest tests/test_inline_buttons.py -v
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

Add to telegram_client.py after send_image:

`python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def send_menu_with_buttons(chat_id: int, text: str, buttons: list[list[dict]]) -> None:
    async def _send():
        bot = get_bot()
        keyboard = [
            [InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"])
             for btn in row]
            for row in buttons
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )
        logger.info(f"Menu with buttons sent to {chat_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())
`

- [ ] **Step 4: Run test to verify it passes**

Run: pytest tests/test_inline_buttons.py::TestSendMenuWithButtons -v
Expected: PASS

- [ ] **Step 5: Commit**

`ash
git add telegram_client.py tests/test_inline_buttons.py
git commit -m "feat: add send_menu_with_buttons to telegram_client"
`

---

### Task 2: Add edit_message_text to telegram_client.py

**Files:**
- Modify: telegram_client.py
- Test: tests/test_inline_buttons.py

- [ ] **Step 1: Write the failing test**

`python
class TestEditMessageText:
    @patch("telegram_client.get_bot")
    def test_edit_message_text_calls_bot(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.edit_message_text = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import edit_message_text
        edit_message_text(123456, 789, "New text")

        mock_bot.edit_message_text.assert_called_once()
        call_kwargs = mock_bot.edit_message_text.call_args[1]
        assert call_kwargs["chat_id"] == 123456
        assert call_kwargs["message_id"] == 789
        assert call_kwargs["text"] == "New text"

    @patch("telegram_client.get_bot")
    def test_edit_message_text_converts_chat_id_to_int(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.edit_message_text = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import edit_message_text
        edit_message_text("123456", 789, "Text")

        call_kwargs = mock_bot.edit_message_text.call_args[1]
        assert isinstance(call_kwargs["chat_id"], int)
`

- [ ] **Step 2: Run test to verify it fails**

Run: pytest tests/test_inline_buttons.py::TestEditMessageText -v
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`python
def edit_message_text(chat_id: int, message_id: int, text: str,
                      buttons: list[list[dict]] | None = None) -> None:
    async def _send():
        bot = get_bot()
        kwargs = {
            "chat_id": int(chat_id),
            "message_id": message_id,
            "text": text,
            "parse_mode": ParseMode.MARKDOWN,
        }
        if buttons:
            keyboard = [
                [InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"])
                 for btn in row]
                for row in buttons
            ]
            kwargs["reply_markup"] = InlineKeyboardMarkup(keyboard)
        await bot.edit_message_text(**kwargs)
        logger.info(f"Message edited for chat_id={chat_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())
`

- [ ] **Step 4: Run test to verify it passes**

Run: pytest tests/test_inline_buttons.py::TestEditMessageText -v
Expected: PASS

- [ ] **Step 5: Commit**

`ash
git add telegram_client.py tests/test_inline_buttons.py
git commit -m "feat: add edit_message_text to telegram_client"
`

---

### Task 3: Add edit_message_reply_markup to telegram_client.py

**Files:**
- Modify: telegram_client.py
- Test: tests/test_inline_buttons.py

- [ ] **Step 1: Write the failing test**

`python
class TestEditMessageReplyMarkup:
    @patch("telegram_client.get_bot")
    def test_edit_reply_markup_calls_bot(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.edit_message_reply_markup = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import edit_message_reply_markup
        buttons = [[{"text": "OK", "callback_data": "btn:ok"}]]
        edit_message_reply_markup(123456, 789, buttons)

        mock_bot.edit_message_reply_markup.assert_called_once()
`

- [ ] **Step 2: Run test to verify it fails**

Run: pytest tests/test_inline_buttons.py::TestEditMessageReplyMarkup -v
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`python
def edit_message_reply_markup(chat_id: int, message_id: int,
                               buttons: list[list[dict]] | None = None) -> None:
    async def _send():
        bot = get_bot()
        if buttons:
            keyboard = [
                [InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"])
                 for btn in row]
                for row in buttons
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            reply_markup = ""
        await bot.edit_message_reply_markup(
            chat_id=int(chat_id),
            message_id=message_id,
            reply_markup=reply_markup,
        )
        logger.info(f"Reply markup edited for chat_id={chat_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())
`

- [ ] **Step 4: Run test to verify it passes**

Run: pytest tests/test_inline_buttons.py::TestEditMessageReplyMarkup -v
Expected: PASS

- [ ] **Step 5: Commit**

`ash
git add telegram_client.py tests/test_inline_buttons.py
git commit -m "feat: add edit_message_reply_markup to telegram_client"
`

---

### Task 4: Add async wrappers and _build_main_menu_buttons to zavu_handlers.py

**Files:**
- Modify: zavu_handlers.py
- Test: tests/test_inline_buttons.py

- [ ] **Step 1: Write the failing test**

`python
class TestMainMenuButtons:
    def test_build_main_menu_buttons_returns_5_rows(self):
        from zavu_handlers import _build_main_menu_buttons
        buttons = _build_main_menu_buttons()
        assert len(buttons) == 5

    def test_build_main_menu_buttons_callback_data(self):
        from zavu_handlers import _build_main_menu_buttons
        buttons = _build_main_menu_buttons()
        assert buttons[0][0]["callback_data"] == "btn:1"
        assert buttons[1][0]["callback_data"] == "btn:2"
        assert buttons[2][0]["callback_data"] == "btn:3"
        assert buttons[3][0]["callback_data"] == "btn:4"
        assert buttons[4][0]["callback_data"] == "btn:5"
`

- [ ] **Step 2: Run test to verify it fails**

Run: pytest tests/test_inline_buttons.py::TestMainMenuButtons -v
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Update import on line 5 of zavu_handlers.py:
`python
from telegram_client import send_text, send_image, send_menu_with_buttons, edit_message_text, edit_message_reply_markup
`

Add helper after SEARCH_PAGE_SIZE:
`python
def _build_main_menu_buttons() -> list[list[dict]]:
    return [
        [{"text": "Buscar persona", "callback_data": "btn:1"}],
        [{"text": "Registrar persona", "callback_data": "btn:2"}],
        [{"text": "Refugios cercanos", "callback_data": "btn:3"}],
        [{"text": "Telefonos de emergencia", "callback_data": "btn:4"}],
        [{"text": "Ayuda", "callback_data": "btn:5"}],
    ]
`

Add async wrappers after send_image_async:
`python
async def send_menu_with_buttons_async(chat_id: str, text: str, buttons: list[list[dict]]) -> None:
    try:
        await asyncio.to_thread(send_menu_with_buttons, chat_id, text, buttons)
    except Exception as e:
        logger.error(f"Failed to send menu with buttons to {chat_id}: {e}")

async def edit_menu_async(chat_id: int, message_id: int, text: str,
                           buttons: list[list[dict]] | None = None) -> None:
    try:
        await asyncio.to_thread(edit_message_text, chat_id, message_id, text, buttons)
    except Exception as e:
        logger.error(f"Failed to edit message for chat_id={chat_id}: {e}")

async def edit_markup_async(chat_id: int, message_id: int,
                             buttons: list[list[dict]] | None = None) -> None:
    try:
        await asyncio.to_thread(edit_message_reply_markup, chat_id, message_id, buttons)
    except Exception as e:
        logger.error(f"Failed to edit reply markup for chat_id={chat_id}: {e}")
`

- [ ] **Step 4: Run test to verify it passes**

Run: pytest tests/test_inline_buttons.py::TestMainMenuButtons -v
Expected: PASS

- [ ] **Step 5: Commit**

`ash
git add zavu_handlers.py tests/test_inline_buttons.py
git commit -m "feat: add _build_main_menu_buttons and async wrappers"
`

---

### Task 5: Update handle_start and handle_menu to use buttons

**Files:**
- Modify: zavu_handlers.py
- Test: tests/test_inline_buttons.py

- [ ] **Step 1: Write the failing test**

`python
class TestHandleStartWithButtons:
    @pytest.mark.asyncio
    async def test_handle_start_sends_menu_with_buttons(self):
        from zavu_handlers import handle_start
        with patch("zavu_handlers.send_menu_with_buttons_async") as mock_send:
            mock_send.return_value = None
            await handle_start("123456")
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_start_edits_when_message_id(self):
        from zavu_handlers import handle_start
        with patch("zavu_handlers.edit_menu_async") as mock_edit:
            mock_edit.return_value = None
            await handle_start("123456", message_id=789)
            mock_edit.assert_called_once()
`

- [ ] **Step 2: Run test to verify it fails**

Run: pytest tests/test_inline_buttons.py::TestHandleStartWithButtons -v
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Modify handle_start (line 97-100):
`python
async def handle_start(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    ReportStateMachine.cancel(chat_id)
    clear_search_state(chat_id)
    buttons = _build_main_menu_buttons()
    if message_id:
        await edit_menu_async(int(chat_id), message_id, MENU_TEXT, buttons)
    else:
        await send_menu_with_buttons_async(chat_id, MENU_TEXT, buttons)
`

Modify handle_menu (line 103-105):
`python
async def handle_menu(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    clear_search_state(chat_id)
    buttons = _build_main_menu_buttons()
    if message_id:
        await edit_menu_async(int(chat_id), message_id, MENU_TEXT, buttons)
    else:
        await send_menu_with_buttons_async(chat_id, MENU_TEXT, buttons)
`

- [ ] **Step 4: Run test to verify it passes**

Run: pytest tests/test_inline_buttons.py::TestHandleStartWithButtons -v
Expected: PASS

- [ ] **Step 5: Commit**

`ash
git add zavu_handlers.py tests/test_inline_buttons.py
git commit -m "feat: handle_start and handle_menu use inline buttons"
`

---

### Task 6: Update handle_menu_registrar with sub-option buttons

**Files:**
- Modify: zavu_handlers.py
- Test: tests/test_inline_buttons.py

- [ ] **Step 1: Write the failing test**

`python
class TestRegistrarSubOptions:
    @pytest.mark.asyncio
    async def test_handle_menu_registrar_sends_sub_buttons(self):
        from zavu_handlers import handle_menu_registrar
        with patch("zavu_handlers.send_menu_with_buttons_async") as mock_send:
            mock_send.return_value = None
            await handle_menu_registrar("123456")
            mock_send.assert_called_once()
            buttons = mock_send.call_args[0][2]
            assert len(buttons) == 2
            assert buttons[0][0]["callback_data"] == "btn:registrar:desaparecido"
            assert buttons[1][0]["callback_data"] == "btn:registrar:encontrado"
`

- [ ] **Step 2: Run test to verify it fails**

Run: pytest tests/test_inline_buttons.py::TestRegistrarSubOptions -v
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Modify handle_menu_registrar (line 108-111):
`python
async def handle_menu_registrar(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    clear_search_state(chat_id)
    _registrar_waiting[chat_id] = True
    sub_buttons = [
        [{"text": "Desaparecido", "callback_data": "btn:registrar:desaparecido"}],
        [{"text": "Encontrado", "callback_data": "btn:registrar:encontrado"}],
    ]
    response = "*Registrar persona*\n\nQue tipo de reporte queres hacer?"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, response, sub_buttons)
    else:
        await send_menu_with_buttons_async(chat_id, response, sub_buttons)
`

- [ ] **Step 4: Run test to verify it passes**

Run: pytest tests/test_inline_buttons.py::TestRegistrarSubOptions -v
Expected: PASS

- [ ] **Step 5: Commit**

`ash
git add zavu_handlers.py tests/test_inline_buttons.py
git commit -m "feat: handle_menu_registrar shows Desaparecido/Encontrado buttons"
`

---

### Task 7: Add sub-option handlers for all 5 menu options

**Files:**
- Modify: zavu_handlers.py
- Test: tests/test_inline_buttons.py

- [ ] **Step 1: Write the failing tests**

`python
class TestSubOptionHandlers:
    @pytest.mark.asyncio
    async def test_handle_buscar_nombre(self):
        from zavu_handlers import handle_buscar_nombre
        with patch("zavu_handlers.edit_menu_async") as mock_edit:
            mock_edit.return_value = None
            await handle_buscar_nombre("123456", message_id=789)
            mock_edit.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_registrar_desaparecido(self):
        from zavu_handlers import handle_registrar_desaparecido
        with patch("zavu_handlers.edit_menu_async") as mock_edit, \
             patch("zavu_handlers.ReportStateMachine") as mock_fsm:
            mock_fsm.start.return_value = "Nombre:"
            mock_edit.return_value = None
            await handle_registrar_desaparecido("123456", message_id=789)
            mock_fsm.start.assert_called_once_with("123456", "desaparecido")

    @pytest.mark.asyncio
    async def test_handle_refugios_caracas(self):
        from zavu_handlers import handle_refugios_caracas
        with patch("zavu_handlers._buscar_refugios") as mockBuscar:
            mockBuscar.return_value = None
            await handle_refugios_caracas("123456")
            mockBuscar.assert_called_once_with("123456", "Caracas")
`

- [ ] **Step 2: Run test to verify it fails**

Run: pytest tests/test_inline_buttons.py::TestSubOptionHandlers -v
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Add all sub-option handlers after handle_menu_registrar:

`python
# Buscar sub-options
async def handle_buscar_nombre(chat_id, text="", message_id=None):
    clear_search_state(chat_id)
    response = "*Buscar persona*\n\nEscribi el nombre de la persona que buscas:"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, response)
    else:
        await send_text_async(chat_id, response)

async def handle_buscar_cedula(chat_id, text="", message_id=None):
    clear_search_state(chat_id)
    response = "*Buscar persona*\n\nEscribi la cedula de la persona que buscas:"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, response)
    else:
        await send_text_async(chat_id, response)

# Registrar sub-options
async def handle_registrar_desaparecido(chat_id, text="", message_id=None):
    clear_search_state(chat_id)
    _registrar_waiting.pop(chat_id, None)
    prompt = ReportStateMachine.start(chat_id, "desaparecido")
    if message_id:
        await edit_menu_async(int(chat_id), message_id, prompt)
    else:
        await send_text_async(chat_id, prompt)

async def handle_registrar_encontrado(chat_id, text="", message_id=None):
    clear_search_state(chat_id)
    _registrar_waiting.pop(chat_id, None)
    prompt = ReportStateMachine.start(chat_id, "encontrado")
    if message_id:
        await edit_menu_async(int(chat_id), message_id, prompt)
    else:
        await send_text_async(chat_id, prompt)

# Refugios sub-options
async def handle_refugios_caracas(chat_id, text="", message_id=None):
    await _buscar_refugios(chat_id, "Caracas")

async def handle_refugios_valencia(chat_id, text="", message_id=None):
    await _buscar_refugios(chat_id, "Valencia")

async def handle_refugios_maracaibo(chat_id, text="", message_id=None):
    await _buscar_refugios(chat_id, "Maracaibo")

async def handle_refugios_otra(chat_id, text="", message_id=None):
    _refugios_waiting[chat_id] = True
    response = "*Refugios cercanos*\n\nEscribe el nombre de tu ciudad:"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, response)
    else:
        await send_text_async(chat_id, response)

# Emergencia sub-options
async def handle_emergencia_bomberos(chat_id, text="", message_id=None):
    clear_search_state(chat_id)
    await send_text_async(chat_id, "*Bomberos*\n\nBuscando telefonos...")
    telefonos = await acopiove.buscar_telefonos()
    respuesta = "*Telefonos de emergencia*\n\n"
    for tel in (telefonos or [])[:4]:
        respuesta += f"{acopiove.formatear_telefono(tel)}\n\n"
    await send_text_async(chat_id, respuesta)

async def handle_emergencia_policia(chat_id, text="", message_id=None):
    clear_search_state(chat_id)
    await send_text_async(chat_id, "*Policia*\n\nBuscando telefonos...")
    telefonos = await acopiove.buscar_telefonos()
    respuesta = "*Telefonos de emergencia*\n\n"
    for tel in (telefonos or [])[:4]:
        respuesta += f"{acopiove.formatear_telefono(tel)}\n\n"
    await send_text_async(chat_id, respuesta)

async def handle_emergencia_cruz_roja(chat_id, text="", message_id=None):
    clear_search_state(chat_id)
    await send_text_async(chat_id, "*Cruz Roja*\n\nBuscando telefonos...")
    telefonos = await acopiove.buscar_telefonos()
    respuesta = "*Telefonos de emergencia*\n\n"
    for tel in (telefonos or [])[:4]:
        respuesta += f"{acopiove.formatear_telefono(tel)}\n\n"
    await send_text_async(chat_id, respuesta)

async def handle_emergencia_todos(chat_id, text="", message_id=None):
    await handle_emergencia(chat_id, text)

# Ayuda sub-options
async def handle_ayuda_buscar(chat_id, text="", message_id=None):
    response = "*Como buscar personas*\n\n1. Toca *Buscar persona*\n2. Escribi nombre o cedula\n3. Resultados de 4 fuentes"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, response)
    else:
        await send_text_async(chat_id, response)

async def handle_ayuda_reportar(chat_id, text="", message_id=None):
    response = "*Como reportar personas*\n\n1. Toca *Registrar persona*\n2. Selecciona tipo\n3. Segui los pasos"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, response)
    else:
        await send_text_async(chat_id, response)

async def handle_ayuda_fuentes(chat_id, text="", message_id=None):
    response = "*Fuentes de datos*\n\nReportaVNZLA, found-people-ve-bot, AcopioVE, DB local"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, response)
    else:
        await send_text_async(chat_id, response)
`

- [ ] **Step 4: Run tests to verify they pass**

Run: pytest tests/test_inline_buttons.py::TestSubOptionHandlers -v
Expected: PASS

- [ ] **Step 5: Commit**

`ash
git add zavu_handlers.py tests/test_inline_buttons.py
git commit -m "feat: add all sub-option handlers for inline buttons"
`

---

### Task 8: Update HANDLER_MAP with new routes

**Files:**
- Modify: zavu_handlers.py
- Test: tests/test_inline_buttons.py

- [ ] **Step 1: Write the failing test**

`python
class TestHandlerMap:
    def test_handler_map_has_btn_routes(self):
        from zavu_handlers import HANDLER_MAP
        assert "btn:1" in HANDLER_MAP
        assert "btn:registrar:desaparecido" in HANDLER_MAP
        assert "btn:ayuda:fuentes" in HANDLER_MAP
`

- [ ] **Step 2: Run test to verify it fails**

Run: pytest tests/test_inline_buttons.py::TestHandlerMap -v
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Replace HANDLER_MAP in zavu_handlers.py (line 387-410):

`python
HANDLER_MAP = {
    "start": handle_start,
    "menu:buscar": handle_buscar_button,
    "menu:registrar": handle_menu_registrar,
    "menu:refugios": handle_refugios,
    "menu:emergencia": handle_emergencia,
    "ayuda": handle_ayuda,
    "info": handle_info,
    "emergencia": handle_emergencia,
    "refugios": handle_refugios,
    "registrar_cmd": handle_registrar_cmd,
    "button:menu": handle_menu,
    "button:menu:registrar": handle_menu_registrar,
    "button:ayuda": handle_ayuda,
    "button:buscar": handle_buscar_button,
    "buscar": handle_buscar,
    "free_text": handle_free_text,
    "photo": handle_photo,
    "search:more": handle_search_more,
    "search:new": handle_search_new,
    "search:menu": handle_search_menu,
    "reportar:step:text": handle_reportar_text,
    # Inline buttons - menu
    "btn:1": handle_buscar_button,
    "btn:2": handle_menu_registrar,
    "btn:3": handle_refugios,
    "btn:4": handle_emergencia,
    "btn:5": handle_ayuda,
    # Inline buttons - sub-options
    "btn:buscar:nombre": handle_buscar_nombre,
    "btn:buscar:cedula": handle_buscar_cedula,
    "btn:registrar:desaparecido": handle_registrar_desaparecido,
    "btn:registrar:encontrado": handle_registrar_encontrado,
    "btn:refugios:caracas": handle_refugios_caracas,
    "btn:refugios:valencia": handle_refugios_valencia,
    "btn:refugios:maracaibo": handle_refugios_maracaibo,
    "btn:refugios:otra": handle_refugios_otra,
    "btn:emergencia:bomberos": handle_emergencia_bomberos,
    "btn:emergencia:policia": handle_emergencia_policia,
    "btn:emergencia:cruz_roja": handle_emergencia_cruz_roja,
    "btn:emergencia:todos": handle_emergencia_todos,
    "btn:ayuda:buscar": handle_ayuda_buscar,
    "btn:ayuda:reportar": handle_ayuda_reportar,
    "btn:ayuda:fuentes": handle_ayuda_fuentes,
}
`

- [ ] **Step 4: Run test to verify it passes**

Run: pytest tests/test_inline_buttons.py::TestHandlerMap -v
Expected: PASS

- [ ] **Step 5: Commit**

`ash
git add zavu_handlers.py tests/test_inline_buttons.py
git commit -m "feat: add btn:* routes to HANDLER_MAP"
`

---

### Task 9: Update webhook to extract message_id and route btn: callbacks

**Files:**
- Modify: zavu_webhook.py
- Test: tests/test_inline_buttons.py

- [ ] **Step 1: Write the failing test**

`python
class TestWebhookCallbackRouting:
    def test_route_telegram_btn_prefix(self):
        from zavu_webhook import _route_telegram
        assert _route_telegram("btn:1") == "btn:1"
        assert _route_telegram("btn:registrar:desaparecido") == "btn:registrar:desaparecido"

    def test_route_telegram_existing_routes_still_work(self):
        from zavu_webhook import _route_telegram
        assert _route_telegram("/start") == "start"
        assert _route_telegram("1") == "menu:buscar"
`

- [ ] **Step 2: Run test to verify it fails**

Run: pytest tests/test_inline_buttons.py::TestWebhookCallbackRouting -v
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Modify _route_telegram in zavu_webhook.py (add after line 34):
`python
    # Callbacks de botones inline
    if text.startswith("btn:"):
        return text
`

Modify telegram_webhook to extract message_id (around line 83-91):
`python
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = str(cb["message"]["chat"]["id"])
        text = cb.get("data", "")
        callback_query_id = cb["id"]
        message_id = cb["message"]["message_id"]
    else:
        chat_id = str(message["chat"]["id"])
        text = message.get("text", "")
        callback_query_id = None
        message_id = None
`

Modify handler calls to pass message_id:
`python
        if active_route:
            handler = HANDLER_MAP.get("reportar:step:text")
            if handler:
                await handler(chat_id, text, message_id=message_id)
        else:
            handler_name = _route_telegram(text) or get_search_results_route(chat_id, text)
            if handler_name:
                handler = HANDLER_MAP.get(handler_name)
                if handler:
                    await handler(chat_id, text, message_id=message_id)
`

- [ ] **Step 4: Run test to verify it passes**

Run: pytest tests/test_inline_buttons.py::TestWebhookCallbackRouting -v
Expected: PASS

- [ ] **Step 5: Commit**

`ash
git add zavu_webhook.py tests/test_inline_buttons.py
git commit -m "feat: webhook extracts message_id and routes btn:* callbacks"
`

---

### Task 10: Run all tests and verify no regressions

- [ ] **Step 1: Run the full test suite**

Run: pytest tests/ -v
Expected: All tests pass

- [ ] **Step 2: Fix any failures**

- [ ] **Step 3: Final commit if needed**

`ash
git add -A
git commit -m "fix: resolve test failures for inline buttons"
`

---

### Task 11: Manual testing in Telegram

- [ ] **Step 1: Start the bot locally**

Run: uvicorn zavu_webhook:app --host 0.0.0.0 --port 8443

- [ ] **Step 2: Test /start with buttons**

- [ ] **Step 3: Test each menu button**

- [ ] **Step 4: Test sub-options**

- [ ] **Step 5: Test fallback without message_id**

---

## Summary

| Task | Description | Est. Time |
|---|---|---|
| 1 | send_menu_with_buttons | 15 min |
| 2 | edit_message_text | 15 min |
| 3 | edit_message_reply_markup | 10 min |
| 4 | async wrappers + _build_main_menu_buttons | 15 min |
| 5 | handle_start + handle_menu with buttons | 15 min |
| 6 | handle_menu_registrar sub-options | 15 min |
| 7 | All sub-option handlers | 30 min |
| 8 | HANDLER_MAP updates | 10 min |
| 9 | Webhook routing btn:* | 15 min |
| 10 | Run all tests | 10 min |
| 11 | Manual testing | 20 min |
| **Total** | | **~3.5h** |
