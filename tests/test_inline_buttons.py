import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestSendMenuWithButtons:
    @patch("telegram_client.get_bot")
    def test_send_menu_with_buttons_calls_bot(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import send_menu_with_buttons
        buttons = [[{"text": "Buscar", "callback_data": "btn:1"}]]
        send_menu_with_buttons(123456, "Menu text", buttons)

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == 123456
        assert call_kwargs["text"] == "Menu text"
        assert call_kwargs["reply_markup"] is not None

    @patch("telegram_client.get_bot")
    def test_send_menu_with_buttons_builds_keyboard(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import send_menu_with_buttons
        buttons = [
            [{"text": "Buscar", "callback_data": "btn:1"}],
            [{"text": "Ayuda", "callback_data": "btn:5"}],
        ]
        send_menu_with_buttons(123456, "Menu", buttons)

        call_kwargs = mock_bot.send_message.call_args[1]
        markup = call_kwargs["reply_markup"]
        assert len(markup.inline_keyboard) == 2
        assert markup.inline_keyboard[0][0].text == "Buscar"
        assert markup.inline_keyboard[0][0].callback_data == "btn:1"
