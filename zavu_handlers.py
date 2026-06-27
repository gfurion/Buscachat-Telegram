import asyncio
import logging

from zavu_client import send_text, send_buttons
from zavu_router import get_chat_id
from services.found_people_api import FoundPeopleAPI

logger = logging.getLogger(__name__)
api = FoundPeopleAPI()

MENU_TEXT = (
    "*BuscaChat - Reunificacion Familiar*\n\n"
    "Soy tu asistente para buscar personas desaparecidas o reportar "
    "personas encontradas tras el terremoto en Venezuela.\n\n"
    "Selecciona una opcion:\n"
    "1. *Buscar persona*\n"
    "2. *Registrar persona*\n"
    "3. *Ayuda*\n\n"
    "Escribe el numero de la opcion:"
)

REGISTRAR_TEXT = (
    "*Registrar persona*\n\n"
    "Que tipo de persona quieres registrar?\n"
    "/registrar desaparecido - Persona desaparecida\n"
    "/registrar encontrado - Persona encontrada\n"
    "/start - Volver al menu principal"
)

AYUDA_TEXT = (
    "*Ayuda - BuscaChat*\n\n"
    "*Como funciona:*\n"
    "- Usa *Buscar* para encontrar personas por nombre o cedula\n"
    "- Usa *Registrar* para reportar una persona desaparecida o encontrada\n\n"
    "*Comandos:*\n"
    "/start - Menu principal\n"
    "/buscar [nombre] - Buscar persona"
)

RESULTADO_TEXT = "\nEscribe *1* para buscar otra vez o *2* para volver al menu."


async def handle_start(event: dict) -> None:
    chat_id = get_chat_id(event)
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
            "Envia el nombre o cedula de la persona que buscas.\n"
            "Ejemplo: Maria Perez",
        )
        return

    await _realizar_busqueda(chat_id, query)


async def handle_buscar_button(event: dict) -> None:
    chat_id = get_chat_id(event)
    await send_text_async(
        chat_id,
        "*Buscar persona*\n\nEscribe el nombre o cedula de la persona que buscas:",
    )


async def handle_free_text(event: dict) -> None:
    chat_id = get_chat_id(event)
    query = event["data"].get("text", "").strip()

    if len(query) < 2:
        await send_text_async(chat_id, "Escribe al menos 2 caracteres para buscar.")
        return

    await _realizar_busqueda(chat_id, query)


async def handle_photo(event: dict) -> None:
    pass


async def _realizar_busqueda(chat_id: str, query: str) -> None:
    await send_text_async(chat_id, "Buscando...")

    resultados = await api.buscar(query)

    if not resultados:
        await send_text_async(
            chat_id,
            f"No encontre resultados para *{query}*.\n\n"
            "Intenta con otro nombre o cedula.",
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
    await send_text_async(
        chat_id,
        "*Funcionalidad en desarrollo*\n\n"
        "El flujo de registro estara disponible pronto.\n\n"
        "Mientras tanto, usa /buscar para encontrar personas.\n"
        "Escribe /start para volver al menu.",
    )


async def send_text_async(chat_id: str, text: str) -> None:
    await asyncio.to_thread(send_text, chat_id, text)


async def send_buttons_async(chat_id: str, text: str, buttons: list) -> None:
    await asyncio.to_thread(send_text, chat_id, text)


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
}
