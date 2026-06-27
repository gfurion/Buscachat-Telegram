import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler

from keyboards.teclados import menu_principal, menu_registrar

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome = (
        "*BuscaChat - Reunificacion Familiar*\n\n"
        "Soy tu asistente para buscar personas desaparecidas o reportar "
        "personas encontradas tras el terremoto en Venezuela.\n\n"
        "Selecciona una opcion del menu:"
    )
    await update.message.reply_text(
        welcome,
        parse_mode="Markdown",
        reply_markup=menu_principal(),
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    welcome = (
        "*BuscaChat - Menu principal*\n\n"
        "Selecciona una opcion:"
    )
    await query.edit_message_text(
        welcome,
        parse_mode="Markdown",
        reply_markup=menu_principal(),
    )


async def menu_registrar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "*Registrar persona*\n\n"
        "Que tipo de persona quieres registrar?",
        parse_mode="Markdown",
        reply_markup=menu_registrar(),
    )


async def ayuda_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    texto = (
        "*Ayuda - BuscaChat*\n\n"
        "*Como funciona:*\n"
        "- Usa *Buscar* para encontrar personas por nombre o cedula\n"
        "- Puedes enviar una *foto* directamente para buscar por rostro\n"
        "- Usa *Registrar* para reportar una persona desaparecida o encontrada\n\n"
        "*Comandos:*\n"
        "/start - Menu principal\n"
        "/buscar [nombre] - Buscar persona\n"
        "/cancel - Cancelar operacion actual"
    )
    await query.edit_message_text(
        texto,
        parse_mode="Markdown",
        reply_markup=menu_principal(),
    )


start_handler = CommandHandler("start", start)
menu_handler = CallbackQueryHandler(menu_callback, pattern="^menu$")
menu_registrar_handler = CallbackQueryHandler(menu_registrar_callback, pattern="^menu:registrar$")
ayuda_handler = CallbackQueryHandler(ayuda_callback, pattern="^ayuda$")
