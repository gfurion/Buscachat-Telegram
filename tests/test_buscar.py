import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message
from telegram.ext import ContextTypes
from handlers.buscar import buscar, texto_libre


def make_message(text):
    msg = MagicMock(spec=Message)
    msg.text = text
    msg.reply_text = AsyncMock()
    return msg


@pytest.mark.asyncio
async def test_buscar_with_args():
    update = MagicMock(spec=Update)
    update.message = make_message("buscar Maria")
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = ["Maria", "Perez"]

    with patch(
        "handlers.buscar.api.buscar",
        new_callable=AsyncMock,
        return_value=[
            {
                "fullName": "Maria Perez",
                "documentId": "12345678",
                "relevantInfo": "Hospital",
                "sourceUrl": "https://example.com",
            }
        ],
    ):
        await buscar(update, context)

    update.message.reply_text.assert_called()


@pytest.mark.asyncio
async def test_buscar_without_args():
    update = MagicMock(spec=Update)
    update.message = make_message("/buscar")
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []

    await buscar(update, context)

    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args
    assert "nombre o cedula" in call_args[0][0]


@pytest.mark.asyncio
async def test_texto_libre():
    update = MagicMock(spec=Update)
    update.message = make_message("Juan Lopez")
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    with patch(
        "handlers.buscar.api.buscar",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await texto_libre(update, context)

    update.message.reply_text.assert_called()
