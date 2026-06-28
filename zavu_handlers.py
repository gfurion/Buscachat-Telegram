import asyncio
import logging

import aiohttp

from zavu_client import send_text, send_buttons
from zavu_router import get_chat_id
from services.face_matching import FaceMatcher
from services.acopiove_api import AcopioVEAPI
from services.people_search import PeopleSearchAggregator
from zavu_state import ReportStateMachine

logger = logging.getLogger(__name__)
people_search = PeopleSearchAggregator()
acopiove = AcopioVEAPI()
face_matcher = FaceMatcher()

_refugios_waiting: dict[str, bool] = {}
_search_results_state: dict[str, dict] = {}
SEARCH_PAGE_SIZE = 5

MENU_TEXT = (
    "🔍 *BuscaChat — Reunificacion Familiar*\n\n"
    "Asistente para buscar y reportar personas\n"
    "tras el terremoto en Venezuela 🇻🇪\n\n"
    "*¿Que queres hacer?*\n\n"
    "1️⃣ *Buscar persona* — por nombre o cedula\n"
    "2️⃣ *Registrar persona* — desaparecida o encontrada\n"
    "3️⃣ *Refugios cercanos* — centros de ayuda\n"
    "4️⃣ *Telefonos de emergencia*\n"
    "5️⃣ *Ayuda* — como funciona el bot\n\n"
    "Escribi el numero:"
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
    "▸ /emergencia — Telefonos de emergencia"
)

RESULTADO_TEXT = "\n🔁 Escribe *2* para hacer otra busqueda o *3* para volver al menu."


def clear_search_state(chat_id: str) -> None:
    _search_results_state.pop(chat_id, None)


def get_search_results_route(chat_id: str, event: dict) -> str | None:
    if chat_id not in _search_results_state:
        return None

    data = event.get("data", {})
    if data.get("messageType") != "text":
        return None

    text = data.get("text", "").strip()
    if text == "1":
        return "search:more"
    if text == "2":
        return "search:new"
    if text == "3":
        return "search:menu"
    if text in ("/cancel", "Cancelar"):
        return "search:menu"
    return None


async def handle_start(event: dict) -> None:
    chat_id = get_chat_id(event)
    ReportStateMachine.cancel(chat_id)
    clear_search_state(chat_id)
    await send_text_async(chat_id, MENU_TEXT)


async def handle_menu(event: dict) -> None:
    chat_id = get_chat_id(event)
    clear_search_state(chat_id)
    await send_text_async(chat_id, MENU_TEXT)


async def handle_menu_registrar(event: dict) -> None:
    chat_id = get_chat_id(event)
    clear_search_state(chat_id)
    await send_text_async(chat_id, REGISTRAR_TEXT)


async def handle_ayuda(event: dict) -> None:
    chat_id = get_chat_id(event)
    clear_search_state(chat_id)
    await send_text_async(chat_id, AYUDA_TEXT)


async def handle_buscar(event: dict) -> None:
    chat_id = get_chat_id(event)
    clear_search_state(chat_id)
    text = event["data"].get("text", "").strip()
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


async def handle_buscar_button(event: dict) -> None:
    chat_id = get_chat_id(event)
    clear_search_state(chat_id)
    await send_text_async(
        chat_id,
        "*Buscar persona*\n\nEscribi el nombre o cedula de la persona que buscas:",
    )


async def handle_free_text(event: dict) -> None:
    chat_id = get_chat_id(event)
    query = event["data"].get("text", "").strip()

    if len(query) < 2:
        await send_text_async(chat_id, "Escribi al menos 2 caracteres para buscar.")
        return

    if _refugios_waiting.pop(chat_id, None):
        await _buscar_refugios(chat_id, query)
        return

    await _realizar_busqueda(chat_id, query)


async def handle_photo(event: dict) -> None:
    chat_id = get_chat_id(event)
    media_url = event["data"].get("mediaUrl", "")

    if not media_url:
        await send_text_async(chat_id, "No se pudo obtener la imagen.")
        return

    await send_text_async(chat_id, "Analizando imagen...")

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(media_url) as resp:
                if resp.status != 200:
                    await send_text_async(chat_id, "No se pudo descargar la imagen.")
                    return
                image_bytes = await resp.read()
    except Exception as e:
        logger.error(f"Error downloading image from {media_url}: {e}")
        await send_text_async(chat_id, "Error al descargar la imagen. Proba de nuevo.")
        return

    probe = face_matcher.extract_embedding(image_bytes)
    if probe is None:
        await send_text_async(
            chat_id,
            "No se detecto ningun rostro en la foto.\n\n"
            "Asegurate de enviar una foto clara del rostro de la persona.",
        )
        return

    await send_text_async(chat_id, "Buscando coincidencias...")

    matches = face_matcher.buscar_personas(probe)

    if not matches:
        await send_text_async(
            chat_id,
            "No se encontraron coincidencias con esa foto.\n\n"
            "Escribi *1* para buscar por texto o *2* para volver al menu.",
        )
        return

    respuesta = "*Resultados por busqueda facial*\n\n"
    for i, (persona, score) in enumerate(matches[:5], 1):
        respuesta += f"{i}. *{persona.nombre}* (similitud: {score:.0%})\n"
        if persona.cedula:
            respuesta += f"   Cedula: {persona.cedula}\n"
        if persona.ubicacion:
            respuesta += f"   Ubicacion: {persona.ubicacion}\n"
        respuesta += "\n"

    if len(matches) > 5:
        respuesta += f"... y {len(matches) - 5} resultados mas\n\n"

    respuesta += "Escribi *1* para buscar por texto o *2* para volver al menu."
    await send_text_async(chat_id, respuesta)


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

    respuesta = _format_search_page(query, resultados, 0)

    _search_results_state[chat_id] = {
        "query": query,
        "results": resultados,
        "next_index": min(SEARCH_PAGE_SIZE, len(resultados)),
    }
    await send_text_async(chat_id, respuesta)


async def handle_search_more(event: dict) -> None:
    chat_id = get_chat_id(event)
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

    response = _format_search_page(state["query"], results, next_index)
    state["next_index"] = min(next_index + SEARCH_PAGE_SIZE, len(results))
    await send_text_async(chat_id, response)


async def handle_search_new(event: dict) -> None:
    chat_id = get_chat_id(event)
    clear_search_state(chat_id)
    await send_text_async(
        chat_id,
        "*Buscar persona*\n\nEscribi el nombre o cedula de la persona que buscas:",
    )


async def handle_search_menu(event: dict) -> None:
    chat_id = get_chat_id(event)
    clear_search_state(chat_id)
    await send_text_async(chat_id, MENU_TEXT)


def _format_search_page(query: str, results: list, start_index: int) -> str:
    end_index = min(start_index + SEARCH_PAGE_SIZE, len(results))
    response = f"*Resultados para {query}*\n\n"

    for i, persona in enumerate(results[start_index:end_index], start_index + 1):
        response += f"{i}. {people_search.formatear_resultado(persona)}\n\n"

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

    return response


async def handle_registrar_cmd(event: dict) -> None:
    chat_id = get_chat_id(event)
    clear_search_state(chat_id)
    text = event["data"].get("text", "").strip()

    if "encontrado" in text:
        tipo = "encontrado"
    else:
        tipo = "desaparecido"

    prompt = ReportStateMachine.start(chat_id, tipo)
    await send_text_async(chat_id, prompt)


async def handle_reportar_text(event: dict) -> None:
    chat_id = get_chat_id(event)
    text = event["data"].get("text", "").strip()

    if not text:
        await send_text_async(chat_id, "Escribi una respuesta valida.")
        return

    response = ReportStateMachine.handle_text(chat_id, text)

    if response is None:
        # State was canceled (via /start, /cancel, or "Cancelar")
        await send_text_async(chat_id, MENU_TEXT)
        return

    await send_text_async(chat_id, response)


async def handle_reportar_photo(event: dict) -> None:
    chat_id = get_chat_id(event)
    media_url = event["data"].get("mediaUrl", "")

    if not media_url:
        await send_text_async(chat_id, "No se pudo obtener la imagen. Proba de nuevo o escribi /skip.")
        return

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(media_url) as resp:
                if resp.status != 200:
                    await send_text_async(chat_id, "No se pudo descargar la imagen. Proba de nuevo o escribi /skip.")
                    return
                image_bytes = await resp.read()
    except Exception as e:
        logger.error(f"Error downloading image from {media_url}: {e}")
        await send_text_async(chat_id, "Error al descargar la imagen. Proba de nuevo o escribi /skip.")
        return

    probe = face_matcher.extract_embedding(image_bytes)
    if probe is not None:
        ReportStateMachine.set_embedding(chat_id, probe)

    response = ReportStateMachine.handle_photo(chat_id, media_url)

    if response is None:
        return

    await send_text_async(chat_id, response)


async def handle_emergencia(event: dict) -> None:
    chat_id = get_chat_id(event)
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


async def handle_refugios(event: dict) -> None:
    chat_id = get_chat_id(event)
    clear_search_state(chat_id)
    text = event["data"].get("text", "").strip()
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


async def handle_refugios_ciudad(event: dict) -> None:
    chat_id = get_chat_id(event)
    text = event["data"].get("text", "").strip()

    if len(text) < 2:
        await send_text_async(chat_id, "Escribi el nombre de una ciudad (minimo 2 caracteres).")
        return

    await _buscar_refugios(chat_id, text)


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


async def send_text_async(chat_id: str, text: str) -> None:
    try:
        await asyncio.to_thread(send_text, chat_id, text)
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")


async def send_buttons_async(chat_id: str, text: str, buttons: list) -> None:
    await asyncio.to_thread(send_buttons, chat_id, text, buttons)


HANDLER_MAP = {
    "start": handle_start,
    "menu:buscar": handle_buscar_button,
    "menu:registrar": handle_menu_registrar,
    "menu:refugios": handle_refugios,
    "menu:emergencia": handle_emergencia,
    "ayuda": handle_ayuda,
    "emergencia": handle_emergencia,
    "refugios": handle_refugios,
    "registrar_cmd": handle_registrar_cmd,
    "button:menu": handle_menu,
    "button:menu:registrar": handle_menu_registrar,
    "button:ayuda": handle_ayuda,
    "button:buscar": handle_buscar_button,
    "button:reportar:desaparecido": handle_menu,
    "button:reportar:encontrado": handle_menu,
    "buscar": handle_buscar,
    "free_text": handle_free_text,
    "photo": handle_photo,
    "search:more": handle_search_more,
    "search:new": handle_search_new,
    "search:menu": handle_search_menu,
    # State machine handlers
    "reportar:step:text": handle_reportar_text,
    "reportar:step:foto": handle_reportar_photo,
}
