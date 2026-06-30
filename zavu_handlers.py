import asyncio
import logging

from cachetools import TTLCache
from zavu_client import send_text, send_image
from services.database import get_db
from services.face_matching import FaceMatcher
from services.acopiove_api import AcopioVEAPI
from services.people_search import PeopleSearchAggregator
from zavu_state import ReportStateMachine

logger = logging.getLogger(__name__)
people_search = PeopleSearchAggregator(db=get_db())
acopiove = AcopioVEAPI()

_refugios_waiting: TTLCache[str, bool] = TTLCache(maxsize=10000, ttl=600)
_registrar_waiting: TTLCache[str, bool] = TTLCache(maxsize=10000, ttl=600)
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


async def handle_start(chat_id: str, text: str = "") -> None:
    ReportStateMachine.cancel(chat_id)
    clear_search_state(chat_id)
    await send_text_async(chat_id, MENU_TEXT)


async def handle_menu(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    await send_text_async(chat_id, MENU_TEXT)


async def handle_menu_registrar(chat_id: str, text: str = "") -> None:
    clear_search_state(chat_id)
    _registrar_waiting[chat_id] = True
    await send_text_async(chat_id, REGISTRAR_TEXT)


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
    # State machine handlers
    "reportar:step:text": handle_reportar_text,
}
