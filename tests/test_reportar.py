import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, CallbackQuery, Message
from telegram.ext import ContextTypes
from handlers.reportar import (
    reportar_start,
    recibir_nombre,
    NOMBRE,
    CEDULA,
)


def make_callback_query(data):
    query = MagicMock(spec=CallbackQuery)
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    return query


def make_message(text):
    msg = MagicMock(spec=Message)
    msg.text = text
    msg.reply_text = AsyncMock()
    msg.photo = []
    return msg


@pytest.mark.asyncio
async def test_reportar_start_desaparecido():
    update = MagicMock(spec=Update)
    update.callback_query = make_callback_query("reportar:desaparecido")
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}

    result = await reportar_start(update, context)

    assert result == NOMBRE
    assert context.user_data["tipo"].value == "desaparecido"
    update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_recibir_nombre_valido():
    update = MagicMock(spec=Update)
    update.message = make_message("Maria Perez")
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}

    result = await recibir_nombre(update, context)

    assert result == CEDULA
    assert context.user_data["nombre"] == "Maria Perez"


@pytest.mark.asyncio
async def test_recibir_nombre_corto():
    update = MagicMock(spec=Update)
    update.message = make_message("A")
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}

    result = await recibir_nombre(update, context)

    assert result == NOMBRE
    update.message.reply_text.assert_called_once()
