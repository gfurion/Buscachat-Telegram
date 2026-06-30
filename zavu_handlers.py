import asyncio
import logging

from cachetools import TTLCache
from telegram_client import send_text, send_image, send_menu_with_buttons, edit_message_text, edit_message_reply_markup, get_bot
from services.database import get_db
from services.face_matching import FaceMatcher
from services.acopiove_api import AcopioVEAPI
from services.people_search import PeopleSearchAggregator
from zavu_state import ReportStateMachine
from config import Config
from pathlib import Path
import time

logger = logging.getLogger(__name__)
people_search = PeopleSearchAggregator(db=get_db())
acopiove = AcopioVEAPI()

_refugios_waiting: TTLCache[str, bool] = TTLCache(maxsize=10000, ttl=600)
_registrar_waiting: TTLCache[str, bool] = TTLCache(maxsize=10000, ttl=600)
_search_results_state: dict[str, dict] = {}
SEARCH_PAGE_SIZE = 5


def _build_main_menu_buttons() -> list[list[dict]]:
    return [
        [{"text": "🔍 Buscar persona", "callback_data": "btn:1"}],
        [{"text": "📝 Registrar persona", "callback_data": "btn:2"}],
        [{"text": "🏠 Refugios cercanos", "callback_data": "btn:3"}],
        [{"text": "📞 Telefonos de emergencia", "callback_data": "btn:4"}],
        [{"text": "🆘 Ayuda", "callback_data": "btn:5"}],
    ]


MENU_TEXT = (
    "🔍 *BuscaChat — Reunificacion Familiar*\n\n"
    "Asistente para buscar y reportar personas\n"
    "tras el terremoto en Venezuela 🇻🇪\n\n"
    "Elegí una opción del menú:"
)

REGISTRAR_TEXT = (
    "📝 *Registrar persona*\n\n"
    "¿Que tipo de reporte queres hacer?\n\n"
    "▸ /registrar desaparecido — Persona desaparecida\n"
    "▸ /registrar encontrado — Persona encontrada\n"
    "▸ /start — Volver al menu principal"
)

AYUDA_TEXT = (
    "🆘 *Ayuda — BuscaChat*\n\n"
    "*¿Como funciona?*\n"
    "🔎 *Buscar* — encontra personas por nombre o cedula\n"
    "📝 *Registrar* — reporta una persona desaparecida o encontrada\n"
    "📸 *Foto* — busca por reconocimiento facial\n"
    "🏠 *Refugios* — centros de ayuda cercanos\n"
    "📞 *Emergencia* — telefonos de emergencia\n\n"
    "*Comandos:*\n"
    "▸ /start — Menu principal\n"
    "▸ /buscar \\[nombre\\] — Buscar persona\n"
    "▸ /registrar — Reportar persona\n"
    "▸ /refugios — Refugios cercanos\n"
    "▸ /emergencia — Telefonos de emergencia\n"
    "▸ /info — Fuentes de datos"
)

INFO_TEXT = (
    "📊 *Fuentes de datos de BuscaChat*\n\n"
    "Este bot consulta las siguientes fuentes:\n\n"
    "▸ *ReportaVNZLA* — 15.000+ registros estructurados\n"
    "  (nombre, cedula, edad, ubicacion)\n\n"
    "▸ *found-people-ve-bot* — 35.000+ registros\n"
    "  de 5 plataformas: venezuelatebusca.com,\n"
    "  encuentralos.tecnosoft.dev,\n"
    "  desaparecidosterremotovenezuela.com,\n"
    "  terremotovenezuela.app\n\n"
    "▸ *AcopioVE* — 575 centros de acopio,\n"
    "  refugios y telefonos de emergencia\n\n"
    "Proyecto voluntario de Build 4 Venezuela."
)

RESULTADO_TEXT = "\n🔁 Escribe *2* para hacer otra busqueda o *3* para volver al menu."


def clear_search_state(chat_id: str) -> None:
    _search_results_state.pop(chat_id, None)


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


async def handle_start(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    ReportStateMachine.cancel(chat_id)
    clear_search_state(chat_id)
    buttons = _build_main_menu_buttons()
    if message_id:
        await edit_menu_async(int(chat_id), message_id, MENU_TEXT, buttons)
    else:
        await send_menu_with_buttons_async(chat_id, MENU_TEXT, buttons)


async def handle_menu(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    clear_search_state(chat_id)
    buttons = _build_main_menu_buttons()
    if message_id:
        await edit_menu_async(int(chat_id), message_id, MENU_TEXT, buttons)
    else:
        await send_menu_with_buttons_async(chat_id, MENU_TEXT, buttons)


async def handle_menu_registrar(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    clear_search_state(chat_id)
    _registrar_waiting[chat_id] = True
    sub_buttons = [
        [{"text": "❌ Desaparecido", "callback_data": "btn:registrar:desaparecido"}],
        [{"text": "✅ Encontrado", "callback_data": "btn:registrar:encontrado"}],
        [{"text": "🔙 Volver al menú", "callback_data": "btn:menu"}],
    ]
    response = "*Registrar persona*\n\n¿Qué tipo de reporte querés hacer?"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, response, sub_buttons)
    else:
        await send_menu_with_buttons_async(chat_id, response, sub_buttons)


async def handle_ayuda(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(chat_id, AYUDA_TEXT)


async def handle_info(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(chat_id, INFO_TEXT)


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


async def handle_buscar_button(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(
        chat_id,
        "*Buscar persona*\n\nEscribi el nombre o cedula de la persona que buscas:",
    )


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


async def handle_photo_report(chat_id: str, text: str = "") -> None:
    file_id = text.strip()
    if not file_id:
        await send_text_async(chat_id, "No se recibió la foto. Enviá una foto o /skip para omitir.")
        return

    try:
        bot = get_bot()
        file = await bot.get_file(file_id)
        file_bytes = await file.download_as_bytearray()

        filename = f"{chat_id}_{int(time.time())}.jpg"
        filepath = Config.FOTOS_DIR / filename
        Config.FOTOS_DIR.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(file_bytes)

        response = ReportStateMachine.save_photo(chat_id, str(filepath), file_id)
        if not response:
            await send_text_async(chat_id, "No hay un reporte activo. Usá /start para comenzar.")
            return

        await send_text_async(chat_id, response)
        await send_image_async(chat_id, file_id)

        try:
            matcher = FaceMatcher()
            embedding = matcher.extract_embedding(bytes(file_bytes))
            if embedding is not None:
                logger.info(f"Face embedding extracted for chat_id={chat_id}")
        except Exception as e:
            logger.warning(f"Face extraction failed for chat_id={chat_id}: {e}")

    except Exception as e:
        logger.error(f"Photo download failed for chat_id={chat_id}: {e}")
        await send_text_async(chat_id, "Error al descargar la foto. Escribí /skip para omitir.")


async def handle_photo(chat_id: str, text: str = "") -> None:
    logger.info(f"PHOTO EVENT (free search): chat_id={chat_id}")
    await send_text_async(
        chat_id,
        "La busqueda por foto no esta disponible por ahora.\n\n"
        "Usa /buscar con nombre o cedula para buscar personas.",
    )


async def _realizar_busqueda(chat_id: str, query: str) -> None:
    clear_search_state(chat_id)
    await send_text_async(chat_id, "Buscando...")

    resultados = await people_search.buscar(query)

    if not resultados:
        await send_text_async(
            chat_id,
            f"No encontre resultados para *{query}*.\n\n"
            "Proba con otro nombre o cedula.",
        )
        return

    respuesta, fotos = _format_search_page(query, resultados, 0)

    _search_results_state[chat_id] = {
        "query": query,
        "results": resultados,
        "next_index": min(SEARCH_PAGE_SIZE, len(resultados)),
    }
    await send_text_async(chat_id, respuesta)
    for foto_url in fotos:
        await send_image_async(chat_id, foto_url)


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


async def handle_search_new(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(
        chat_id,
        "*Buscar persona*\n\nEscribi el nombre o cedula de la persona que buscas:",
    )


async def handle_search_menu(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(chat_id, MENU_TEXT)


def _format_search_page(query: str, results: list, start_index: int) -> tuple[str, list[str]]:
    end_index = min(start_index + SEARCH_PAGE_SIZE, len(results))
    response = f"*Resultados para {query}*\n\n"

    photo_urls: list[str] = []
    for i, persona in enumerate(results[start_index:end_index], start_index + 1):
        response += f"{i}. {people_search.formatear_resultado(persona)}\n\n"
        if getattr(persona, "foto_path", ""):
            photo_urls.append(persona.foto_path)

    total = len(results)
    shown = end_index
    remaining = total - shown

    response += f"Mostre {shown} de {total} resultados.\n\n"
    if remaining > 0:
        next_count = min(SEARCH_PAGE_SIZE, remaining)
        response += (
            f"Escribe *1* para ver {next_count} mas, "
            "*2* para hacer otra busqueda o *3* para volver al menu."
        )
    else:
        response += "Escribe *2* para hacer otra busqueda o *3* para volver al menu."

    return response, photo_urls


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


async def _buscar_refugios(chat_id: str, ciudad: str) -> None:
    await send_text_async(chat_id, f"Buscando refugios en {ciudad}...")

    puntos = await acopiove.buscar_puntos(tipo="refugio", ciudad=ciudad)

    if not puntos:
        await send_text_async(
            chat_id,
            f"No se encontraron refugios en *{ciudad}*.\n\n"
            "Intenta con otra ciudad o escribe /start para volver al menu.",
        )
        return

    respuesta = f"🏠 *Refugios en {ciudad}*\n\n"
    for punto in puntos[:5]:
        respuesta += f"{acopiove.formatear_punto(punto)}\n\n"

    if len(puntos) > 5:
        respuesta += f"... y {len(puntos) - 5} mas\n\n"

    respuesta += "Escribe /start para volver al menu."
    await send_text_async(chat_id, respuesta)


async def handle_btn_registrar_desaparecido(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    _registrar_waiting.pop(chat_id, None)
    prompt = ReportStateMachine.start(chat_id, "desaparecido")
    await send_text_async(chat_id, prompt)


async def handle_btn_registrar_encontrado(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    _registrar_waiting.pop(chat_id, None)
    prompt = ReportStateMachine.start(chat_id, "encontrado")
    await send_text_async(chat_id, prompt)


async def handle_btn_buscar_nombre(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    await send_text_async(chat_id, "🔍 *Buscar por nombre*\n\nEscribí el nombre de la persona que buscás:")


async def handle_btn_buscar_cedula(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    await send_text_async(chat_id, "🔍 *Buscar por cédula*\n\nEscribí el número de cédula de la persona que buscás:")


async def handle_btn_buscar_foto(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    await send_text_async(chat_id, "🔍 *Buscar por foto*\n\nAdjuntá una foto de la persona que buscás.")


async def handle_btn_refugios_ciudad(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    await send_text_async(chat_id, "🏠 *Refugios por ciudad*\n\nEscribí el nombre de la ciudad para buscar refugios cercanos:")


async def handle_btn_refugios_mapa(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    await send_text_async(chat_id, "🏠 *Mapa de refugios*\n\nEscribí tu ubicación para ver refugios cercanos en el mapa:")


async def handle_btn_emergencia_medica(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    await send_text_async(chat_id, "🏥 *Emergencia médica*\n\n📞 *171* — Bomberos\n📞 *128* — Cruz Roja\n📞 *129* — Ambulancia")


async def handle_btn_emergencia_policial(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    await send_text_async(chat_id, "🚔 *Emergencia policial*\n\n📞 *123* — Policía Nacional\n📞 *147* — Policía Municipal")


async def handle_btn_emergencia_bomberos(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    await send_text_async(chat_id, "🚒 *Bomberos*\n\n📞 *171* — Bomberos nacionales")


async def handle_btn_ayuda_como_usar(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    await send_text_async(chat_id, "❓ *Cómo usar BuscaChat*\n\n1️⃣ Usá /start para ver el menú\n2️⃣ Elegí una opción con los botones\n3️⃣ Seguí las instrucciones paso a paso")


async def handle_btn_ayuda_privacidad(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    await send_text_async(chat_id, "🔒 *Privacidad*\n\nTus datos son confidenciales.\nNo se comparten con terceros.\nSolo se usan para la búsqueda de personas.")


async def handle_btn_ayuda_contacto(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    await send_text_async(chat_id, "📞 *Contacto*\n\n📧 @BuscaChatVzla_bot\n🌐 buscachat-telegram-production.up.railway.app")


async def handle_btn_buscar(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    clear_search_state(chat_id)
    sub_buttons = [
        [{"text": "🔍 Buscar por nombre", "callback_data": "btn:buscar:nombre"}],
        [{"text": "🆔 Buscar por cédula", "callback_data": "btn:buscar:cedula"}],
        [{"text": "📸 Buscar por foto", "callback_data": "btn:buscar:foto"}],
        [{"text": "🔙 Volver al menú", "callback_data": "btn:menu"}],
    ]
    response = "*Buscar persona*\n\n¿Cómo querés realizar la búsqueda?"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, response, sub_buttons)
    else:
        await send_menu_with_buttons_async(chat_id, response, sub_buttons)


async def handle_btn_refugios(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    clear_search_state(chat_id)
    sub_buttons = [
        [{"text": "🏙️ Refugios por ciudad", "callback_data": "btn:refugios:ciudad"}],
        [{"text": "🗺️ Ver mapa de refugios", "callback_data": "btn:refugios:mapa"}],
        [{"text": "🔙 Volver al menú", "callback_data": "btn:menu"}],
    ]
    response = "*Refugios cercanos*\n\nSelecciona una opción:"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, response, sub_buttons)
    else:
        await send_menu_with_buttons_async(chat_id, response, sub_buttons)


async def handle_btn_emergencia(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    clear_search_state(chat_id)
    sub_buttons = [
        [{"text": "🏥 Emergencia Médica", "callback_data": "btn:emergencia:medica"}],
        [{"text": "🚔 Emergencia Policial", "callback_data": "btn:emergencia:policial"}],
        [{"text": "🚒 Bomberos", "callback_data": "btn:emergencia:bomberos"}],
        [{"text": "🔙 Volver al menú", "callback_data": "btn:menu"}],
    ]
    response = "*Teléfonos de emergencia*\n\nSelecciona la categoría:"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, response, sub_buttons)
    else:
        await send_menu_with_buttons_async(chat_id, response, sub_buttons)


async def handle_btn_ayuda(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    sub_buttons = [
        [{"text": "❓ Cómo usar el bot", "callback_data": "btn:ayuda:como_usar"}],
        [{"text": "🔒 Políticas de privacidad", "callback_data": "btn:ayuda:privacidad"}],
        [{"text": "📞 Soporte / Contacto", "callback_data": "btn:ayuda:contacto"}],
        [{"text": "🔙 Volver al menú", "callback_data": "btn:menu"}],
    ]
    response = "*Ayuda y Soporte*\n\n¿En qué podemos ayudarte?"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, response, sub_buttons)
    else:
        await send_menu_with_buttons_async(chat_id, response, sub_buttons)


async def send_text_async(chat_id: str, text: str) -> None:
    try:
        await asyncio.to_thread(send_text, chat_id, text)
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")


async def send_image_async(chat_id: str, image_url: str, caption: str = "") -> None:
    try:
        await asyncio.to_thread(send_image, chat_id, image_url, caption)
    except Exception as e:
        logger.error(f"Failed to send image to {chat_id}: {e}")


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
    "photo:report": handle_photo_report,
    "search:more": handle_search_more,
    "search:new": handle_search_new,
    "search:menu": handle_search_menu,
    # State machine handlers
    "reportar:step:text": handle_reportar_text,
    # Inline button routing
    "btn:1": handle_btn_buscar,
    "btn:2": handle_menu_registrar,
    "btn:3": handle_btn_refugios,
    "btn:4": handle_btn_emergencia,
    "btn:5": handle_btn_ayuda,
    "btn:buscar:nombre": handle_btn_buscar_nombre,
    "btn:buscar:cedula": handle_btn_buscar_cedula,
    "btn:buscar:foto": handle_btn_buscar_foto,
    "btn:registrar:desaparecido": handle_btn_registrar_desaparecido,
    "btn:registrar:encontrado": handle_btn_registrar_encontrado,
    "btn:refugios:ciudad": handle_btn_refugios_ciudad,
    "btn:refugios:mapa": handle_btn_refugios_mapa,
    "btn:emergencia:medica": handle_btn_emergencia_medica,
    "btn:emergencia:policial": handle_btn_emergencia_policial,
    "btn:emergencia:bomberos": handle_btn_emergencia_bomberos,
    "btn:ayuda:como_usar": handle_btn_ayuda_como_usar,
    "btn:ayuda:privacidad": handle_btn_ayuda_privacidad,
    "btn:ayuda:contacto": handle_btn_ayuda_contacto,
    "btn:menu": handle_menu,
}
