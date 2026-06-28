import asyncio
import logging

from zavu_client import send_text
from zavu_router import get_chat_id
from config import Config
from services.found_people_api import FoundPeopleAPI
from services.acopiove_api import AcopioVEAPI
from services.reportavnzla_api import ReportaVNZLAAPI
from zavu_state import ReportStateMachine

logger = logging.getLogger(__name__)
api = FoundPeopleAPI()
acopiove = AcopioVEAPI()
reportavnzla = ReportaVNZLAAPI()

_refugios_waiting: dict[str, bool] = {}
_registrar_waiting: dict[str, bool] = {}

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

RESULTADO_TEXT = "\n🔁 Escribi *1* para buscar otra vez o *2* para volver al menu."


async def handle_start(event: dict) -> None:
    chat_id = get_chat_id(event)
    ReportStateMachine.cancel(chat_id)
    await send_text_async(chat_id, MENU_TEXT)


async def handle_menu(event: dict) -> None:
    chat_id = get_chat_id(event)
    await send_text_async(chat_id, MENU_TEXT)


async def handle_menu_registrar(event: dict) -> None:
    chat_id = get_chat_id(event)
    _registrar_waiting[chat_id] = True
    await send_text_async(chat_id, REGISTRAR_TEXT)


async def handle_ayuda(event: dict) -> None:
    chat_id = get_chat_id(event)
    await send_text_async(chat_id, AYUDA_TEXT)


async def handle_buscar(event: dict) -> None:
    chat_id = get_chat_id(event)
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


async def handle_photo(event: dict) -> None:
    chat_id = get_chat_id(event)
    logger.info(f"PHOTO EVENT (free search): data keys={list(event.get('data', {}).keys())}")
    await send_text_async(
        chat_id,
        "La busqueda por foto no esta disponible por ahora.\n\n"
        "Usa /buscar con nombre o cedula para buscar personas.",
    )


async def _realizar_busqueda(chat_id: str, query: str) -> None:
    await send_text_async(chat_id, "Buscando...")

    resultados_api = await api.buscar(query)
    resultados_rvnzla = await reportavnzla.buscar_personas(query=query)

    seen = set()
    respuesta = f"*Resultados para {query}*\n\n"
    count = 0

    for persona in resultados_rvnzla[:5]:
        nombre = (persona.get("nombre", "") + " " + persona.get("apellido", "")).strip()
        if nombre and nombre.lower() not in seen:
            seen.add(nombre.lower())
            count += 1
            respuesta += f"{count}. {reportavnzla.formatear_persona(persona)}\n\n"

    for persona in resultados_api:
        if count >= 5:
            break
        nombre = persona.get("fullName", "")
        if nombre and nombre.lower() not in seen:
            seen.add(nombre.lower())
            count += 1
            respuesta += f"{count}. {api.formatear_resultado(persona)}\n\n"

    if count == 0:
        await send_text_async(
            chat_id,
            f"No encontre resultados para *{query}*.\n\n"
            "Proba con otro nombre o cedula.",
        )
        return

    total_rvnzla = len(resultados_rvnzla)
    total_api = len(resultados_api)
    if total_rvnzla > 5 or total_api > 0:
        extras = sum(1 for _ in [*resultados_rvnzla[5:], *resultados_api] if _.get("fullName") or (_.get("nombre") and _.get("apellido")))
        if extras > 0:
            respuesta += f"... y {extras} resultados mas\n\n"

    respuesta += RESULTADO_TEXT
    await send_text_async(chat_id, respuesta)


async def handle_registrar_cmd(event: dict) -> None:
    chat_id = get_chat_id(event)
    text = event["data"].get("text", "").strip()
    _registrar_waiting.pop(chat_id, None)

    if "encontrado" in text:
        tipo = "encontrado"
    else:
        tipo = "desaparecido"

    logger.info(f"Registrar: text={text[:50]} tipo={tipo} chat_id={chat_id}")
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

    logger.info(f"REPORTAR PHOTO EVENT: data keys={list(event.get('data', {}).keys())}")

    if not media_url:
        await send_text_async(chat_id, "No se pudo obtener la imagen. Proba de nuevo o escribi /skip.")
        return

    response = ReportStateMachine.handle_photo(chat_id, media_url)

    if response is None:
        return

    await send_text_async(chat_id, response)


async def handle_emergencia(event: dict) -> None:
    chat_id = get_chat_id(event)
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
    # State machine handlers
    "reportar:step:text": handle_reportar_text,
    "reportar:step:foto": handle_reportar_photo,
}
