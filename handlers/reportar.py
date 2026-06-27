import logging

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import Config
from models.persona import Persona, TipoReporte
from services.database import Database
from keyboards.teclados import confirmar_teclado, resultado_teclado

logger = logging.getLogger(__name__)

NOMBRE, CEDULA, UBICACION, FOTO, CONFIRMAR = range(5)

db = Database()


async def reportar_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data
    if "desaparecido" in data:
        context.user_data["tipo"] = TipoReporte.DESAPARECIDO
        tipo_text = "desaparecido/a"
    else:
        context.user_data["tipo"] = TipoReporte.ENCONTRADO
        tipo_text = "encontrado/a"

    await query.edit_message_text(
        f"*Reportar persona {tipo_text}*\n\n"
        "Cual es el nombre completo de la persona?",
        parse_mode="Markdown",
    )
    return NOMBRE


async def recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nombre = update.message.text.strip()
    if len(nombre) < 2:
        await update.message.reply_text(
            "El nombre debe tener al menos 2 caracteres. Intenta de nuevo:"
        )
        return NOMBRE

    context.user_data["nombre"] = nombre
    await update.message.reply_text(
        f"Nombre: *{nombre}*\n\n"
        "Cual es el numero de cedula? (Si no sabes, envia /skip)",
        parse_mode="Markdown",
    )
    return CEDULA


async def recibir_cedula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cedula = update.message.text.strip()
    if cedula != "/skip" and not cedula.isdigit():
        await update.message.reply_text(
            "La cedula debe contener solo numeros. Intenta de nuevo o envia /skip:"
        )
        return CEDULA

    context.user_data["cedula"] = "" if cedula == "/skip" else cedula
    await update.message.reply_text(
        "En que ubicacion fue vista por ultima vez? (Si no sabes, envia /skip)"
    )
    return UBICACION


async def recibir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ubicacion = update.message.text.strip()
    if ubicacion == "/skip":
        ubicacion = ""

    context.user_data["ubicacion"] = ubicacion
    await update.message.reply_text(
        "Envia una foto de la persona. (Si no tienes, envia /skip)"
    )
    return FOTO


async def recibir_foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo = update.message.photo[-1]
    file = await photo.get_file()

    Config.ensure_dirs()
    photo_path = Config.FOTOS_DIR / f"{update.effective_user.id}_{photo.file_id}.jpg"
    await file.download_to_drive(str(photo_path))

    context.user_data["foto_path"] = str(photo_path)
    context.user_data["foto_file_id"] = photo.file_id

    return await mostrar_resumen(update, context)


async def skip_foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["foto_path"] = None
    context.user_data["foto_file_id"] = None
    return await mostrar_resumen(update, context)


async def mostrar_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    datos = context.user_data
    tipo = datos.get("tipo", TipoReporte.DESAPARECIDO)
    tipo_text = "desaparecido/a" if tipo == TipoReporte.DESAPARECIDO else "encontrado/a"

    resumen = (
        f"*Resumen del reporte*\n\n"
        f"Tipo: *{tipo_text}*\n"
        f"Nombre: *{datos.get('nombre', '-')}\n"
        f"Cedula: {datos.get('cedula', 'No informada')}\n"
        f"Ubicacion: {datos.get('ubicacion', 'No informada')}\n"
        f"Foto: {'Enviada' if datos.get('foto_path') else 'No enviada'}\n\n"
        "Confirmas el reporte?"
    )
    await update.message.reply_text(
        resumen,
        parse_mode="Markdown",
        reply_markup=confirmar_teclado(),
    )
    return CONFIRMAR


async def confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == "Cancelar":
        context.user_data.clear()
        await update.message.reply_text(
            "Reporte cancelado.",
            reply_markup=None,
        )
        return ConversationHandler.END

    if text != "Confirmar":
        await update.message.reply_text(
            "Por favor, envia Confirmar o Cancelar:"
        )
        return CONFIRMAR

    datos = context.user_data
    persona = Persona(
        nombre=datos.get("nombre", ""),
        cedula=datos.get("cedula", ""),
        ubicacion=datos.get("ubicacion", ""),
        foto_path=datos.get("foto_path"),
        foto_file_id=datos.get("foto_file_id"),
        tipo=datos.get("tipo", TipoReporte.DESAPARECIDO),
        reporter_chat_id=update.effective_chat.id,
    )

    try:
        persona_id = db.guardar_persona(persona)
    except Exception as e:
        logger.error(f"Error saving report: {e}")
        await update.message.reply_text(
            "Error al guardar el reporte. Intenta de nuevo.",
            reply_markup=None,
        )
        return ConversationHandler.END

    tipo_text = "desaparecido/a" if persona.tipo == TipoReporte.DESAPARECIDO else "encontrado/a"
    await update.message.reply_text(
        f"*Reporte guardado correctamente*\n\n"
        f"ID: #{persona_id}\n"
        f"Nombre: {persona.nombre}\n"
        f"Tipo: {tipo_text}\n\n"
        "Si tienes mas informacion, puedes enviarla como mensaje.",
        parse_mode="Markdown",
        reply_markup=resultado_teclado(),
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Operacion cancelada.",
        reply_markup=None,
    )
    return ConversationHandler.END


reportar_conv = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.Regex("^reportar:(desaparecido|encontrado)$"),
            reportar_start,
        ),
    ],
    states={
        NOMBRE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre),
        ],
        CEDULA: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cedula),
            CommandHandler("skip", recibir_cedula),
        ],
        UBICACION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ubicacion),
            CommandHandler("skip", recibir_ubicacion),
        ],
        FOTO: [
            MessageHandler(filters.PHOTO, recibir_foto),
            CommandHandler("skip", skip_foto),
        ],
        CONFIRMAR: [
            MessageHandler(filters.Regex("^(Confirmar|Cancelar)$"), confirmar),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancelar),
        CommandHandler("skip", recibir_cedula),
    ],
)
