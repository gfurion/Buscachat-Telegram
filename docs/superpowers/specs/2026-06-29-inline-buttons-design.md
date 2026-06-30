# Design Spec: Inline Buttons para BuscaChat

**Fecha:** 2026-06-29
**Estado:** Aprobado
**Alcance:** Menu principal + sub-opciones de las 5 opciones

---

## 1. Objetivo

Reemplazar la navegacion por texto libre ("Escribi el numero") por botones inline de Telegram en el menu principal y sub-opciones de cada opcion. Mejorar la UX reduciendo errores de tipeo y haciendo la navigacion tactil.

## 2. Alcance

### Incluido
- Menu principal (/start) con 5 botones inline verticales
- Sub-opciones con botones para cada una de las 5 opciones
- edit_message_text para reemplazar el menu al tocar un boton
- Routing de callbacks con prefijo tn:
- Tests para todas las funciones nuevas

### No incluido
- Botones en resultados de busqueda (pendiente futura iteracion)
- Botones en flujo de registro (solo la seleccion desaparecido/encontrado)
- Reply keyboards (teclado nativo del usuario)

## 3. Arquitectura

### Flujo actual
`
/start -> handle_start() -> send_text(MENU_TEXTO) -> usuario escribe "1"
-> _route_telegram("1") -> handle_buscar_button() -> responde "Escribi el nombre"
`

### Flujo con botones
`
/start -> handle_start() -> send_menu_with_buttons(MENU_TEXTO, BOTONES)
-> usuario toca "Buscar persona" -> callback_data="btn:1"
-> webhook parsea callback_query -> _route_telegram("btn:1") -> handle_buscar_button()
-> edit_message_text("Escribi el nombre") <- reemplaza el menu
`

### Archivos modificados

| Archivo | Cambio |
|---|---|
| telegram_client.py | +3 funciones: send_menu_with_buttons, edit_message_text, edit_message_reply_markup |
| zavu_handlers.py | Firma + message_id, helpers de botones, handlers de sub-opciones |
| zavu_webhook.py | Extraer message_id de callback_query, routing btn:* |
| tests/test_fase_a.py | Tests para funciones nuevas |

## 4. callback_data - Esquema de routing

### Prefijo btn:

Todos los callback_data usan prefijo tn: para distinguirlos de texto libre del usuario.

`
Menu principal:
  "btn:1" -> menu:buscar
  "btn:2" -> menu:registrar
  "btn:3" -> menu:refugios
  "btn:4" -> menu:emergencia
  "btn:5" -> ayuda

Sub-opciones:
  "btn:buscar:nombre"           -> buscar_nombre
  "btn:buscar:cedula"           -> buscar_cedula
  "btn:registrar:desaparecido"  -> registrar_desaparecido
  "btn:registrar:encontrado"    -> registrar_encontrado
  "btn:refugios:caracas"        -> refugios_caracas
  "btn:refugios:valencia"       -> refugios_valencia
  "btn:refugios:maracaibo"      -> refugios_maracaibo
  "btn:refugios:otra"           -> refugios_otra
  "btn:emergencia:bomberos"     -> emergencia_bomberos
  "btn:emergencia:policia"      -> emergencia_policia
  "btn:emergencia:cruz_roja"    -> emergencia_cruz_roja
  "btn:emergencia:todos"        -> emergencia_todos
  "btn:ayuda:buscar"            -> ayuda_buscar
  "btn:ayuda:reportar"          -> ayuda_reportar
  "btn:ayuda:fuentes"           -> ayuda_fuentes
`

### Cambio en _route_telegram()

`python
def _route_telegram(text: str) -> str | None:
    text = text.strip()

    # Callbacks de botones inline
    if text.startswith("btn:"):
        return text

    # ... routing existente sin cambios ...
`

## 5. telegram_client.py - Funciones nuevas

### 5.1 send_menu_with_buttons

`python
def send_menu_with_buttons(chat_id: int, text: str,
                            buttons: list[list[dict]]) -> None:
    """
    Envia mensaje con InlineKeyboardMarkup.
    buttons = [[{"text": "Buscar", "callback_data": "btn:1"}], ...]
    """
`

- Construye InlineKeyboardMarkup a partir de la lista de botones
- Usa ot.send_message() con eply_markup
- Mismo patron sync/async que send_text

### 5.2 edit_message_text

`python
def edit_message_text(chat_id: int, message_id: int, text: str,
                      buttons: list[list[dict]] | None = None) -> None:
    """
    Edita un mensaje existente (reemplaza texto y opcionalmente botones).
    """
`

- Usa ot.edit_message_text() de python-telegram-bot
- Si se pasan botones, actualiza eply_markup con InlineKeyboardMarkup

### 5.3 edit_message_reply_markup

`python
def edit_message_reply_markup(chat_id: int, message_id: int,
                               buttons: list[list[dict]] | None = None) -> None:
    """
    Solo actualiza los botones de un mensaje existente (sin cambiar texto).
    """
`

- Usa ot.edit_message_reply_markup()
- Util para actualizar botones sin cambiar el texto

## 6. zavu_handlers.py - Cambios

### 6.1 Firma actualizada

Todos los handlers reciben message_id como parametro opcional:

`python
async def handle_start(chat_id: str, text: str = "",
                       message_id: int | None = None) -> None
`

### 6.2 Helper _build_main_menu_buttons()

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

### 6.3 Async wrappers

`python
async def send_menu_with_buttons_async(chat_id: str, text: str,
                                        buttons: list[list[dict]]) -> None:
    await asyncio.to_thread(send_menu_with_buttons, chat_id, text, buttons)

async def edit_menu_async(chat_id: int, message_id: int, text: str,
                           buttons: list[list[dict]] | None = None) -> None:
    await asyncio.to_thread(edit_message_text, chat_id, message_id, text, buttons)

async def edit_markup_async(chat_id: int, message_id: int,
                             buttons: list[list[dict]] | None = None) -> None:
    await asyncio.to_thread(edit_message_reply_markup, chat_id, message_id, buttons)
`

### 6.4 handle_start y handle_menu - Cambios

`python
async def handle_start(chat_id: str, text: str = "",
                       message_id: int | None = None) -> None:
    ReportStateMachine.cancel(chat_id)
    clear_search_state(chat_id)
    buttons = _build_main_menu_buttons()
    if message_id:
        await edit_menu_async(chat_id, message_id, MENU_TEXT, buttons)
    else:
        await send_menu_with_buttons_async(chat_id, MENU_TEXT, buttons)
`

### 6.5 Sub-opciones - Ejemplo handle_menu_registrar

`python
async def handle_menu_registrar(chat_id: str, text: str = "",
                                 message_id: int | None = None) -> None:
    sub_buttons = [
        [{"text": "Desaparecido", "callback_data": "btn:registrar:desaparecido"}],
        [{"text": "Encontrado", "callback_data": "btn:registrar:encontrado"}],
    ]
    response = "*Registrar persona*\n\nQue tipo de reporte queres hacer?"
    if message_id:
        await edit_menu_async(chat_id, message_id, response, sub_buttons)
    else:
        await send_menu_with_buttons_async(chat_id, response, sub_buttons)
`

### 6.6 Handlers de sub-opciones

Cada sub-opcion tiene un handler que procesa la accion:

- handle_buscar_nombre -> inicia busqueda por nombre (pide input)
- handle_buscar_cedula -> inicia busqueda por cedula (pide input)
- handle_registrar_desaparecido -> inicia FSM con tipo DESAPARECIDO
- handle_registrar_encontrado -> inicia FSM con tipo ENCONTRADO
- handle_refugios_caracas -> busca refugios en Caracas
- handle_refugios_valencia -> busca refugios en Valencia
- handle_refugios_maracaibo -> busca refugios en Maracaibo
- handle_refugios_otra -> pide nombre de ciudad
- handle_emergencia_bomberos -> muestra telefonos de bomberos
- handle_emergencia_policia -> muestra telefonos de policia
- handle_emergencia_cruz_roja -> muestra telefonos de cruz roja
- handle_emergencia_todos -> muestra todos los telefonos
- handle_ayuda_buscar -> muestra ayuda de busqueda
- handle_ayuda_reportar -> muestra ayuda de reporte
- handle_ayuda_fuentes -> muestra fuentes de datos

### 6.7 HANDLER_MAP - Keys nuevas

`python
HANDLER_MAP = {
    # ... existente ...
    # Sub-opciones
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

## 7. zavu_webhook.py - Cambios

### 7.1 Extraer message_id de callback_query

`python
if "callback_query" in update:
    cb = update["callback_query"]
    chat_id = str(cb["message"]["chat"]["id"])
    text = cb.get("data", "")
    callback_query_id = cb["id"]
    message_id = cb["message"]["message_id"]  # NUEVO
else:
    chat_id = str(message["chat"]["id"])
    text = message.get("text", "")
    callback_query_id = None
    message_id = None
`

### 7.2 Pasar message_id a handlers

`python
handler = HANDLER_MAP.get(handler_name)
if handler:
    await handler(chat_id, text, message_id=message_id)
`

### 7.3 Answer callback con text

`python
if callback_query_id:
    from telegram_client import answer_callback
    answer_callback(callback_query_id, "")
`

## 8. Flujo completo por opcion

### Opcion 1: Buscar persona

`
Menu -> toca "Buscar persona" (btn:1)
-> edit_message_text("Buscar persona\n\nComo queres buscar?")
-> botones: "Por nombre" | "Por cedula"
-> toca "Por nombre" (btn:buscar:nombre)
-> edit_message_text("Escribi el nombre o cedula...")
-> usuario escribe texto -> handle_buscar -> resultados
`

### Opcion 2: Registrar persona

`
Menu -> toca "Registrar persona" (btn:2)
-> edit_message_text("Registrar persona\n\nQue tipo de reporte?")
-> botones: "Desaparecido" | "Encontrado"
-> toca "Desaparecido" (btn:registrar:desaparecido)
-> edit_message_text("Nombre de la persona:")
-> FSM inicia -> 4 pasos
`

### Opcion 3: Refugios

`
Menu -> toca "Refugios cercanos" (btn:3)
-> edit_message_text("Refugios cercanos\n\nEn que ciudad?")
-> botones: "Caracas" | "Valencia" | "Maracaibo" | "Otra ciudad"
-> toca "Valencia" (btn:refugios:valencia)
-> edit_message_text("Buscando refugios en Valencia...")
-> resultados
`

### Opcion 4: Emergencia

`
Menu -> toca "Telefonos de emergencia" (btn:4)
-> edit_message_text("Telefonos de emergencia\n\nCual necesitas?")
-> botones: "Bomberos" | "Policia" | "Cruz Roja" | "Todos"
-> toca "Todos" (btn:emergencia:todos)
-> edit_message_text(con telefonos)
-> sin botones (mensaje informativo)
`

### Opcion 5: Ayuda

`
Menu -> toca "Ayuda" (btn:5)
-> edit_message_text("Ayuda\n\nQue queres saber?")
-> botones: "Como buscar" | "Como reportar" | "Fuentes de datos"
-> toca "Como buscar" (btn:ayuda:buscar)
-> edit_message_text(con instrucciones)
-> sin botones (mensaje informativo)
`

## 9. Tests

| Test | Que verifica |
|---|---|
| test_send_menu_with_buttons | send_menu_with_buttons llama bot.send_message con reply_markup |
| test_edit_message_text | edit_message_text llama bot.edit_message_text |
| test_edit_message_reply_markup | edit_message_reply_markup actualiza solo botones |
| test_handle_start_with_buttons | handle_start envia menu con 5 botones |
| test_handle_start_edits_menu | handle_start edita menu cuando message_id tiene valor |
| test_handle_menu_registrar_suboptions | Muestra botones Desaparecido/Encontrado |
| test_btn_callback_routes | callback_data="btn:1" se enruta correctamente |
| test_btn_registrar_routes | callback_data="btn:registrar:desaparecido" se enruta |
| test_callback_query_extracts_message_id | Webhook extrae message_id de callback_query |

## 10. Riesgos

| Nivel | Riesgo | Mitigacion |
|---|---|---|
| Medio | edit_message_text falla si el mensaje es muy viejo (>48h) | Fallback: enviar nuevo mensaje con send_menu_with_buttons |
| Medio | chat_id como string vs int | send_message acepta ambos, pero edit_message_text necesita int para chat_id - verificar conversion |
| Bajo | Callback data muy largo (>64 bytes) | Nombres cortos: btn:registrar:desaparecido = 30 chars, OK |
| Bajo | Botones no se ven en Telegram Web | Limitacion de Telegram, no del bot |

## 11. Estimacion

| Tarea | Tiempo |
|---|---|
| telegram_client.py - 3 funciones | 30 min |
| zavu_handlers.py - wrappers + helpers + handlers sub-opciones | 1.5h |
| zavu_webhook.py - routing btn:* + message_id | 30 min |
| Tests | 45 min |
| Testing manual en Telegram | 30 min |
| **Total** | **~3.5h** |
