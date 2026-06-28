import asyncio
import logging

import aiohttp

from zavu_client import send_text, send_buttons
from zavu_router import get_chat_id
from config import Config
from services.found_people_api import FoundPeopleAPI
from services.face_matching import FaceMatcher
from zavu_state import ReportStateMachine

logger = logging.getLogger(__name__)
api = FoundPeopleAPI()
face_matcher = FaceMatcher()

MENU_TEXT = (
    "🔍 *BuscaChat — Reunificacion Familiar*\n\n"
    "Asistente para buscar y reportar personas\n"
    "tras el terremoto en Venezuela 🇻🇪\n\n"
    "*¿Que queres hacer?*\n\n"
    "1️⃣ *Buscar persona* — por nombre o cedula\n"
    "2️⃣ *Registrar persona* — desaparecida o encontrada\n"
    "3️⃣ *Ayuda* — como funciona el bot\n\n"
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
    "📸 *Foto* — busca por reconocimiento facial\n\n"
    "*Comandos:*\n"
    "▸ /start — Menu principal\n"
    "▸ /buscar \\[nombre\\] — Buscar persona\n"
    "▸ /registrar — Reportar persona"
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
    await send_text_async(chat_id, "Buscando...")

    resultados = await api.buscar(query)

    if not resultados:
        await send_text_async(
            chat_id,
            f"No encontre resultados para *{query}*.\n\n"
            "Proba con otro nombre o cedula.",
        )
        return

    respuesta = f"*Resultados para {query}*\n\n"
    for i, persona in enumerate(resultados[:5], 1):
        respuesta += f"{i}. {api.formatear_resultado(persona)}\n\n"

    if len(resultados) > 5:
        respuesta += f"... y {len(resultados) - 5} resultados mas\n"

    respuesta += RESULTADO_TEXT
    await send_text_async(chat_id, respuesta)


async def handle_registrar_cmd(event: dict) -> None:
    chat_id = get_chat_id(event)
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

    response = ReportStateMachine.handle_photo(chat_id, media_url)

    if response is None:
        return

    await send_text_async(chat_id, response)


async def send_text_async(chat_id: str, text: str) -> None:
    await asyncio.to_thread(send_text, chat_id, text)


async def send_buttons_async(chat_id: str, text: str, buttons: list) -> None:
    await asyncio.to_thread(send_buttons, chat_id, text, buttons)


HANDLER_MAP = {
    "start": handle_start,
    "menu:buscar": handle_buscar_button,
    "menu:registrar": handle_menu_registrar,
    "ayuda": handle_ayuda,
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
    # State machine handlers
    "reportar:step:text": handle_reportar_text,
    "reportar:step:foto": handle_reportar_photo,
}
