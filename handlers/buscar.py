import logging

from telegram import Update
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from services.found_people_api import FoundPeopleAPI
from services.face_matching import FaceMatcher
from services.database import Database
from keyboards.teclados import resultado_teclado

logger = logging.getLogger(__name__)

api = FoundPeopleAPI()
face_matcher = FaceMatcher()
db = Database()


async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args) if context.args else ""

    if not query:
        await update.message.reply_text(
            "*Buscar persona*\n\n"
            "Envia el nombre o cedula de la persona que buscas.\n"
            "Ejemplo: `/buscar Maria Perez`",
            parse_mode="Markdown",
        )
        return

    await _realizar_busqueda(update, context, query)


async def buscar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "*Buscar persona*\n\n"
        "Escribe el nombre o cedula de la persona que buscas:",
        parse_mode="Markdown",
    )


async def buscar_por_foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    photo = update.message.photo[-1]
    file = await photo.get_file()
    image_bytes = await file.download_as_bytearray()

    probe = face_matcher.extract_embedding(bytes(image_bytes))
    if probe is None:
        await update.message.reply_text("No se detecto ningun rostro en la foto.")
        return

    msg = await update.message.reply_text("Buscando por foto...")

    matches = face_matcher.buscar_personas(probe)

    if not matches:
        await msg.edit_text(
            "No se encontraron coincidencias con esa foto.",
            reply_markup=resultado_teclado(),
        )
        return

    respuesta = "*Resultados por busqueda facial*\n\n"
    for i, (persona, score) in enumerate(matches[:5], 1):
        respuesta += f"{i}. **{persona.nombre}** (similitud: {score:.0%})\n"
        if persona.ubicacion:
            respuesta += f"   Ubicacion: {persona.ubicacion}\n"

    await msg.edit_text(
        respuesta,
        parse_mode="Markdown",
        reply_markup=resultado_teclado(),
    )


async def texto_libre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.message.text.strip()
    if len(query) < 2:
        await update.message.reply_text("Escribe al menos 2 caracteres para buscar.")
        return

    await _realizar_busqueda(update, context, query)


async def _realizar_busqueda(
    update: Update, context: ContextTypes.DEFAULT_TYPE, query: str
) -> None:
    msg = await update.message.reply_text("Buscando...")

    resultados_api = await api.buscar(query)

    if not resultados_api:
        await msg.edit_text(
            f"No encontre resultados para *{query}*.\n\n"
            "Intenta con otro nombre o cedula.",
            parse_mode="Markdown",
            reply_markup=resultado_teclado(),
        )
        return

    respuesta = f"*Resultados para {query}*\n\n"

    for i, persona in enumerate(resultados_api[:5], 1):
        respuesta += f"{i}. {api.formatear_resultado(persona)}\n\n"

    if len(resultados_api) > 5:
        respuesta += f"... y {len(resultados_api) - 5} resultados mas\n"

    await msg.edit_text(
        respuesta,
        parse_mode="Markdown",
        reply_markup=resultado_teclado(),
    )


buscar_handler = CommandHandler("buscar", buscar)
buscar_callback_handler = CallbackQueryHandler(buscar_callback, pattern="^buscar$")
foto_handler = MessageHandler(filters.PHOTO, buscar_por_foto)
texto_libre_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    texto_libre,
)
