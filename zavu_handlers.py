import asyncio
import logging
import httpx

from cachetools import TTLCache
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram_client import get_bot
from services.database import get_db
from services.face_matching import FaceMatcher
from services.acopiove_api import AcopioVEAPI
from services.people_search import PeopleSearchAggregator
from services.venezuela_te_busca_api import VenezuelaTeBuscaAPI
from services.normalizer import escape_md
from zavu_state import ReportStateMachine
from config import Config
from pathlib import Path
import time

logger = logging.getLogger(__name__)
people_search = PeopleSearchAggregator(db=get_db(), venezuela_te_busca=VenezuelaTeBuscaAPI())
acopiove = AcopioVEAPI()

_refugios_waiting: TTLCache[str, bool] = TTLCache(maxsize=10000, ttl=600)
_registrar_waiting: TTLCache[str, bool] = TTLCache(maxsize=10000, ttl=600)
_ciudades_cache: TTLCache[str, list] = TTLCache(maxsize=10, ttl=300)
_search_results_state: dict[str, dict] = {}
_refugios_results_state: dict[str, dict] = {}
SEARCH_PAGE_SIZE = 5
REFUGIOS_PAGE_SIZE = 5


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

    if _registrar_waiting.get(chat_id):
        if query.lower() in ("desaparecido", "encontrado"):
            _registrar_waiting.pop(chat_id, None)
            tipo = query.lower()
            prompt = ReportStateMachine.start(chat_id, tipo)
            await send_text_async(chat_id, prompt)
            return
        elif query.lower() in ("desaparecida", "encontrada"):
            _registrar_waiting.pop(chat_id, None)
            tipo = query.lower().rstrip("a")
            prompt = ReportStateMachine.start(chat_id, tipo)
            await send_text_async(chat_id, prompt)
            return
        else:
            await send_text_async(chat_id, "Por favor seleccioná **Desaparecido** o **Encontrado** usando los botones de abajo.")
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

        if not file.file_path:
            raise RuntimeError("No file_path available for this file")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(file.file_path)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            content_length = int(resp.headers.get("content-length", "0"))

            if content_length > 10 * 1024 * 1024:
                raise RuntimeError("File too large (max 10MB)")

            if content_type not in ("image/jpeg", "image/png", "image/webp"):
                raise RuntimeError(f"Invalid content type: {content_type}")

            file_bytes = resp.content

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

    buttons = _build_search_nav_buttons(chat_id)
    await send_menu_with_buttons_async(chat_id, "¿Qué querés hacer?", buttons)


async def handle_search_more(chat_id: str, text: str = "", message_id: int | None = None) -> None:
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

    buttons = _build_search_nav_buttons(chat_id)
    await send_menu_with_buttons_async(chat_id, "¿Qué querés hacer?", buttons)


async def handle_search_new(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    clear_search_state(chat_id)
    await send_text_async(
        chat_id,
        "*Buscar persona*\n\nEscribi el nombre o cedula de la persona que buscas:",
    )


async def handle_search_menu(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    clear_search_state(chat_id)
    if message_id:
        buttons = _build_main_menu_buttons()
        await edit_menu_async(int(chat_id), message_id, MENU_TEXT, buttons)
    else:
        await send_menu_with_buttons_async(chat_id, MENU_TEXT, _build_main_menu_buttons())


async def handle_search_nav(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    action = text.split(":")[-1] if ":" in text else ""
    if action == "more":
        await handle_search_more(chat_id, "", message_id)
    elif action == "new":
        await handle_search_new(chat_id, "", message_id)
    elif action == "menu":
        await handle_search_menu(chat_id, "", message_id)


def _build_search_nav_buttons(chat_id: str) -> list[list[dict]]:
    state = _search_results_state.get(chat_id)
    buttons = []
    if state and state["next_index"] < len(state["results"]):
        buttons.append([{"text": "➡️ Siguiente", "callback_data": "btn:search:more"}])
    nav_row = []
    nav_row.append({"text": "🆕 Nueva búsqueda", "callback_data": "btn:search:new"})
    nav_row.append({"text": "🏠 Menú", "callback_data": "btn:search:menu"})
    buttons.append(nav_row)
    return buttons


def _format_search_page(query: str, results: list, start_index: int) -> tuple[str, list[str]]:
    end_index = min(start_index + SEARCH_PAGE_SIZE, len(results))
    response = f"*Resultados para {escape_md(query)}*\n\n"

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
        acopios = await acopiove.buscar_puntos(tipo="acopio", ciudad=ciudad)
        if acopios:
            _refugios_results_state.pop(chat_id, None)
            respuesta = f"🏠 *No hay refugios en {ciudad}*, pero hay {len(acopios)} centros de acopio:\n\n"
            for punto in acopios[:5]:
                respuesta += f"{acopiove.formatear_punto(punto)}\n\n"
            if len(acopios) > 5:
                respuesta += f"... y {len(acopios) - 5} mas\n\n"
            respuesta += "Escribe /start para volver al menu."
            await send_text_async(chat_id, respuesta)
            return

        await send_text_async(
            chat_id,
            f"No se encontraron refugios ni centros de acopio en *{ciudad}*.\n\n"
            "Intenta con otra ciudad o escribe /start para volver al menu.",
        )
        return

    _refugios_results_state[chat_id] = {
        "ciudad": ciudad,
        "results": puntos,
        "next_index": min(REFUGIOS_PAGE_SIZE, len(puntos)),
        "tipo": "refugio",
    }

    respuesta = f"🏠 *Refugios en {ciudad}*\n\n"
    for punto in puntos[:REFUGIOS_PAGE_SIZE]:
        respuesta += f"{acopiove.formatear_punto(punto)}\n\n"

    await send_text_async(chat_id, respuesta)
    await _send_refugios_nav_buttons(chat_id)


async def _send_refugios_nav_buttons(chat_id: str) -> None:
    state = _refugios_results_state.get(chat_id)
    if not state:
        return
    remaining = len(state["results"]) - state["next_index"]
    buttons = []
    if remaining > 0:
        buttons.append([{"text": f"➡️ Siguiente ({remaining} más)", "callback_data": "btn:refugios:more"}])
    buttons.append([{"text": "🏠 Menú", "callback_data": "btn:menu"}])
    await send_menu_with_buttons_async(chat_id, "¿Qué querés hacer?", buttons)


async def handle_refugios_more(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    state = _refugios_results_state.get(chat_id)
    if not state:
        await send_text_async(chat_id, MENU_TEXT)
        return

    next_index = state["next_index"]
    results = state["results"]

    if next_index >= len(results):
        await send_text_async(chat_id, "No hay más refugios disponibles.")
        return

    ciudad = state["ciudad"]
    respuesta = f"🏠 *Refugios en {ciudad}*\n\n"
    end = min(next_index + REFUGIOS_PAGE_SIZE, len(results))
    for punto in results[next_index:end]:
        respuesta += f"{acopiove.formatear_punto(punto)}\n\n"

    state["next_index"] = end
    await send_text_async(chat_id, respuesta)
    await _send_refugios_nav_buttons(chat_id)


async def handle_btn_registrar_desaparecido(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    _registrar_waiting.pop(chat_id, None)
    prompt = ReportStateMachine.start(chat_id, "desaparecido")
    if message_id:
        await edit_menu_async(int(chat_id), message_id, prompt, None)
    else:
        await send_text_async(chat_id, prompt)


async def handle_btn_registrar_encontrado(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    _registrar_waiting.pop(chat_id, None)
    prompt = ReportStateMachine.start(chat_id, "encontrado")
    if message_id:
        await edit_menu_async(int(chat_id), message_id, prompt, None)
    else:
        await send_text_async(chat_id, prompt)


async def handle_btn_buscar_nombre(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    texto = "🔍 *Buscar por nombre*\n\nEscribí el nombre de la persona que buscás:"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, texto, None)
    else:
        await send_text_async(chat_id, texto)


async def handle_btn_buscar_cedula(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    texto = "🔍 *Buscar por cédula*\n\nEscribí el número de cédula de la persona que buscás:"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, texto, None)
    else:
        await send_text_async(chat_id, texto)


async def handle_btn_buscar_foto(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    texto = "🔍 *Buscar por foto*\n\nAdjuntá una foto de la persona que buscás."
    if message_id:
        await edit_menu_async(int(chat_id), message_id, texto, None)
    else:
        await send_text_async(chat_id, texto)


async def handle_refugios_ciudades(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    clear_search_state(chat_id)

    page = 0
    if text.startswith("btn:refugios:ciudades:page:"):
        try:
            page = int(text.rsplit(":", 1)[-1])
        except (ValueError, IndexError):
            page = 0

    await send_text_async(chat_id, "Obteniendo lista de ciudades...")

    try:
        ciudades_data = _ciudades_cache.get("all")
        if ciudades_data is None:
            puntos = await acopiove.buscar_puntos(tipo="refugio")
            if not puntos:
                puntos = await acopiove.buscar_puntos()
            city_counts: dict[str, int] = {}
            for p in puntos:
                ciudad = p.get("ciudad", "").strip()
                if not ciudad:
                    continue
                city_counts[ciudad] = city_counts.get(ciudad, 0) + 1
            ciudades_data = sorted(city_counts.items(), key=lambda x: (-x[1], x[0]))
            _ciudades_cache["all"] = ciudades_data

        if not ciudades_data:
            await send_text_async(chat_id, "No se encontraron ciudades con datos disponibles.")
            return

        PAGE_SIZE = 10
        total = len(ciudades_data)
        start = page * PAGE_SIZE
        end = min(start + PAGE_SIZE, total)

        if start >= total:
            await send_text_async(chat_id, "No hay más ciudades disponibles.")
            return

        page_ciudades = ciudades_data[start:end]
        buttons = []
        for ciudad, count in page_ciudades:
            buttons.append([{"text": f"🏙️ {ciudad} ({count})", "callback_data": f"btn:refugios:ciudad:{ciudad}"}])

        nav_row = []
        if page > 0:
            nav_row.append({"text": "⬅️ Anterior", "callback_data": f"btn:refugios:ciudades:page:{page - 1}"})
        if end < total:
            nav_row.append({"text": "➡️ Siguiente", "callback_data": f"btn:refugios:ciudades:page:{page + 1}"})
        if nav_row:
            buttons.append(nav_row)
        buttons.append([{"text": "🔙 Volver al menú", "callback_data": "btn:menu"}])

        response = f"*Refugios por ciudad*\n\nSeleccioná una ciudad ({start + 1}-{end} de {total}):"
        if message_id:
            await edit_menu_async(int(chat_id), message_id, response, buttons)
        else:
            await send_menu_with_buttons_async(chat_id, response, buttons)
    except Exception as e:
        logger.error(f"Error fetching cities: {e}")
        await send_text_async(chat_id, "Error al obtener lista de ciudades. Escribí /start para volver.")


async def handle_refugios_ciudad_item(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    prefix = "btn:refugios:ciudad:"
    ciudad = text[len(prefix):] if text.startswith(prefix) else text
    if not ciudad:
        await send_text_async(chat_id, "No se especificó una ciudad.")
        return
    await _buscar_refugios(chat_id, ciudad)


async def handle_btn_emergencia_medica(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    texto = "🏥 *Emergencia médica*\n\n📞 *171* — Bomberos\n📞 *128* — Cruz Roja\n📞 *129* — Ambulancia"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, texto, None)
    else:
        await send_text_async(chat_id, texto)


async def handle_btn_emergencia_policial(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    texto = "🚔 *Emergencia policial*\n\n📞 *123* — Policía Nacional\n📞 *147* — Policía Municipal"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, texto, None)
    else:
        await send_text_async(chat_id, texto)


async def handle_btn_emergencia_bomberos(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    texto = "🚒 *Bomberos*\n\n📞 *171* — Bomberos nacionales"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, texto, None)
    else:
        await send_text_async(chat_id, texto)


async def handle_btn_ayuda_como_usar(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    texto = "❓ *Cómo usar BuscaChat*\n\n1️⃣ Usá /start para ver el menú\n2️⃣ Elegí una opción con los botones\n3️⃣ Seguí las instrucciones paso a paso"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, texto, None)
    else:
        await send_text_async(chat_id, texto)


async def handle_btn_ayuda_privacidad(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    texto = "🔒 *Privacidad*\n\nTus datos son confidenciales.\nNo se comparten con terceros.\nSolo se usan para la búsqueda de personas."
    if message_id:
        await edit_menu_async(int(chat_id), message_id, texto, None)
    else:
        await send_text_async(chat_id, texto)


async def handle_btn_ayuda_contacto(chat_id: str, text: str = "", message_id: int | None = None) -> None:
    texto = "📞 *Contacto*\n\n📧 @BuscaChatVzla_bot\n🌐 buscachat-telegram-production.up.railway.app"
    if message_id:
        await edit_menu_async(int(chat_id), message_id, texto, None)
    else:
        await send_text_async(chat_id, texto)


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
        [{"text": "🏙️ Refugios y centros de acopio", "callback_data": "btn:refugios:ciudades"}],
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
        bot = get_bot()
        await bot.send_message(
            chat_id=int(chat_id),
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")


async def send_image_async(chat_id: str, image: str, caption: str = "") -> None:
    try:
        bot = get_bot()
        await bot.send_photo(
            chat_id=int(chat_id),
            photo=image,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"Failed to send image to {chat_id}: {e}")


async def send_menu_with_buttons_async(chat_id: str, text: str, buttons: list[list[dict]]) -> None:
    try:
        keyboard = [
            [InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"])
             for btn in row]
            for row in buttons
        ]
        bot = get_bot()
        await bot.send_message(
            chat_id=int(chat_id),
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception as e:
        logger.error(f"Failed to send menu with buttons to {chat_id}: {e}")


async def edit_menu_async(chat_id: int, message_id: int, text: str,
                           buttons: list[list[dict]] | None = None) -> None:
    try:
        kwargs = {
            "chat_id": chat_id,
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
        bot = get_bot()
        await bot.edit_message_text(**kwargs)
    except Exception as e:
        logger.error(f"Failed to edit message for chat_id={chat_id}: {e}")


async def edit_markup_async(chat_id: int, message_id: int,
                             buttons: list[list[dict]] | None = None) -> None:
    try:
        if buttons:
            keyboard = [
                [InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"])
                 for btn in row]
                for row in buttons
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            reply_markup = None
        bot = get_bot()
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f"Failed to edit reply markup for chat_id={chat_id}: {e}")


async def answer_callback_async(callback_query_id: str) -> None:
    try:
        bot = get_bot()
        await bot.answer_callback_query(callback_query_id=callback_query_id)
    except Exception as e:
        logger.error(f"Failed to answer callback {callback_query_id}: {e}")


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
    "btn:refugios:ciudades": handle_refugios_ciudades,
    "btn:refugios:ciudades:page": handle_refugios_ciudades,
    "btn:refugios:ciudad:*": handle_refugios_ciudad_item,
    "btn:refugios:more": handle_refugios_more,
    "btn:emergencia:medica": handle_btn_emergencia_medica,
    "btn:emergencia:policial": handle_btn_emergencia_policial,
    "btn:emergencia:bomberos": handle_btn_emergencia_bomberos,
    "btn:ayuda:como_usar": handle_btn_ayuda_como_usar,
    "btn:ayuda:privacidad": handle_btn_ayuda_privacidad,
    "btn:ayuda:contacto": handle_btn_ayuda_contacto,
    "btn:search:more": handle_search_nav,
    "btn:search:new": handle_search_nav,
    "btn:search:menu": handle_search_nav,
    "btn:menu": handle_menu,
}
