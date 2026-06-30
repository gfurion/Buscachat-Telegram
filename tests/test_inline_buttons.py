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


class TestEditMessageText:
    @patch("telegram_client.get_bot")
    def test_edit_message_text_calls_bot(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.edit_message_text = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import edit_message_text
        edit_message_text(123456, 789, "New text")

        mock_bot.edit_message_text.assert_called_once()
        call_kwargs = mock_bot.edit_message_text.call_args[1]
        assert call_kwargs["chat_id"] == 123456
        assert call_kwargs["message_id"] == 789
        assert call_kwargs["text"] == "New text"

    @patch("telegram_client.get_bot")
    def test_edit_message_text_with_buttons(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.edit_message_text = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import edit_message_text
        buttons = [[{"text": "OK", "callback_data": "btn:ok"}]]
        edit_message_text(123456, 789, "Updated", buttons)

        call_kwargs = mock_bot.edit_message_text.call_args[1]
        assert call_kwargs["reply_markup"] is not None

    @patch("telegram_client.get_bot")
    def test_edit_message_text_converts_chat_id_to_int(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.edit_message_text = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import edit_message_text
        edit_message_text("123456", 789, "Text")

        call_kwargs = mock_bot.edit_message_text.call_args[1]
        assert isinstance(call_kwargs["chat_id"], int)


class TestEditMessageReplyMarkup:
    @patch("telegram_client.get_bot")
    def test_edit_reply_markup_calls_bot(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.edit_message_reply_markup = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import edit_message_reply_markup
        buttons = [[{"text": "OK", "callback_data": "btn:ok"}]]
        edit_message_reply_markup(123456, 789, buttons)

        mock_bot.edit_message_reply_markup.assert_called_once()
        call_kwargs = mock_bot.edit_message_reply_markup.call_args[1]
        assert call_kwargs["chat_id"] == 123456
        assert call_kwargs["message_id"] == 789

    @patch("telegram_client.get_bot")
    def test_edit_reply_markup_removes_buttons(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.edit_message_reply_markup = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import edit_message_reply_markup
        edit_message_reply_markup(123456, 789, None)

        call_kwargs = mock_bot.edit_message_reply_markup.call_args[1]
        assert call_kwargs["reply_markup"] == ""
