import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update
from telegram.ext import ContextTypes
from handlers.start import start


@pytest.mark.asyncio
async def test_start_sends_welcome():
    update = MagicMock(spec=Update)
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    await start(update, context)

    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args
    assert "BuscaChat" in call_args[0][0]
    assert call_args[1]["parse_mode"] == "Markdown"
