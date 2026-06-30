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


class TestMainMenuButtons:
    def test_build_main_menu_buttons_returns_5_rows(self):
        from zavu_handlers import _build_main_menu_buttons
        buttons = _build_main_menu_buttons()
        assert len(buttons) == 5

    def test_build_main_menu_buttons_callback_data(self):
        from zavu_handlers import _build_main_menu_buttons
        buttons = _build_main_menu_buttons()
        assert buttons[0][0]["callback_data"] == "btn:1"
        assert buttons[1][0]["callback_data"] == "btn:2"
        assert buttons[2][0]["callback_data"] == "btn:3"
        assert buttons[3][0]["callback_data"] == "btn:4"
        assert buttons[4][0]["callback_data"] == "btn:5"

    def test_build_main_menu_buttons_have_text(self):
        from zavu_handlers import _build_main_menu_buttons
        buttons = _build_main_menu_buttons()
        for row in buttons:
            assert "text" in row[0]
            assert len(row[0]["text"]) > 0


class TestHandleStartWithButtons:
    @pytest.mark.asyncio
    async def test_handle_start_sends_menu_with_buttons(self):
        from zavu_handlers import handle_start
        with patch("zavu_handlers.send_menu_with_buttons_async") as mock_send:
            mock_send.return_value = None
            await handle_start("123456")
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "123456"
            assert len(call_args[0][2]) == 5

    @pytest.mark.asyncio
    async def test_handle_start_edits_when_message_id(self):
        from zavu_handlers import handle_start
        with patch("zavu_handlers.edit_menu_async") as mock_edit:
            mock_edit.return_value = None
            await handle_start("123456", message_id=789)
            mock_edit.assert_called_once()
            call_args = mock_edit.call_args
            assert call_args[0][0] == 123456
            assert call_args[0][1] == 789

    @pytest.mark.asyncio
    async def test_handle_menu_sends_menu_with_buttons(self):
        from zavu_handlers import handle_menu
        with patch("zavu_handlers.send_menu_with_buttons_async") as mock_send:
            mock_send.return_value = None
            await handle_menu("123456")
            mock_send.assert_called_once()


class TestRegistrarSubOptions:
    @pytest.mark.asyncio
    async def test_handle_menu_registrar_sends_sub_buttons(self):
        from zavu_handlers import handle_menu_registrar
        with patch("zavu_handlers.send_menu_with_buttons_async") as mock_send:
            mock_send.return_value = None
            await handle_menu_registrar("123456")
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            buttons = call_args[0][2]
            assert len(buttons) == 2
            assert buttons[0][0]["callback_data"] == "btn:registrar:desaparecido"
            assert buttons[1][0]["callback_data"] == "btn:registrar:encontrado"

    @pytest.mark.asyncio
    async def test_handle_menu_registrar_edits_when_message_id(self):
        from zavu_handlers import handle_menu_registrar
        with patch("zavu_handlers.edit_menu_async") as mock_edit:
            mock_edit.return_value = None
            await handle_menu_registrar("123456", message_id=789)
            mock_edit.assert_called_once()


class TestRegistrarDesaparecidoEncontrado:
    @pytest.mark.asyncio
    async def test_btn_registrar_desaparecido_sends_text(self):
        from zavu_handlers import handle_btn_registrar_desaparecido
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_registrar_desaparecido("123456")
            mock_send.assert_called_once()
            assert "nombre" in mock_send.call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_btn_registrar_encontrado_sends_text(self):
        from zavu_handlers import handle_btn_registrar_encontrado
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_registrar_encontrado("123456")
            mock_send.assert_called_once()
            assert "nombre" in mock_send.call_args[0][1].lower()


class TestBuscarSubOptions:
    @pytest.mark.asyncio
    async def test_btn_buscar_nombre_sends_text(self):
        from zavu_handlers import handle_btn_buscar_nombre
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_buscar_nombre("123456")
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_btn_buscar_cedula_sends_text(self):
        from zavu_handlers import handle_btn_buscar_cedula
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_buscar_cedula("123456")
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_btn_buscar_foto_sends_text(self):
        from zavu_handlers import handle_btn_buscar_foto
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_buscar_foto("123456")
            mock_send.assert_called_once()


class TestRefugiosSubOptions:
    @pytest.mark.asyncio
    async def test_btn_refugios_ciudad_sends_text(self):
        from zavu_handlers import handle_btn_refugios_ciudad
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_refugios_ciudad("123456")
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_btn_refugios_mapa_sends_text(self):
        from zavu_handlers import handle_btn_refugios_mapa
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_refugios_mapa("123456")
            mock_send.assert_called_once()


class TestEmergenciaSubOptions:
    @pytest.mark.asyncio
    async def test_btn_emergencia_medica_sends_text(self):
        from zavu_handlers import handle_btn_emergencia_medica
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_emergencia_medica("123456")
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_btn_emergencia_policial_sends_text(self):
        from zavu_handlers import handle_btn_emergencia_policial
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_emergencia_policial("123456")
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_btn_emergencia_bomberos_sends_text(self):
        from zavu_handlers import handle_btn_emergencia_bomberos
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_emergencia_bomberos("123456")
            mock_send.assert_called_once()


class TestAyudaSubOptions:
    @pytest.mark.asyncio
    async def test_btn_ayuda_como_usar_sends_text(self):
        from zavu_handlers import handle_btn_ayuda_como_usar
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_ayuda_como_usar("123456")
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_btn_ayuda_privacidad_sends_text(self):
        from zavu_handlers import handle_btn_ayuda_privacidad
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_ayuda_privacidad("123456")
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_btn_ayuda_contacto_sends_text(self):
        from zavu_handlers import handle_btn_ayuda_contacto
        with patch("zavu_handlers.send_text_async") as mock_send:
            mock_send.return_value = None
            await handle_btn_ayuda_contacto("123456")
            mock_send.assert_called_once()


class TestHandlerMapInlineButtons:
    def test_handler_map_has_all_btn_keys(self):
        from zavu_handlers import HANDLER_MAP
        expected_keys = [
            "btn:1", "btn:2", "btn:3", "btn:4", "btn:5",
            "btn:buscar:nombre", "btn:buscar:cedula", "btn:buscar:foto",
            "btn:registrar:desaparecido", "btn:registrar:encontrado",
            "btn:refugios:ciudad", "btn:refugios:mapa",
            "btn:emergencia:medica", "btn:emergencia:policial", "btn:emergencia:bomberos",
            "btn:ayuda:como_usar", "btn:ayuda:privacidad", "btn:ayuda:contacto"
        ]
        for key in expected_keys:
            assert key in HANDLER_MAP, f"Key {key} not found in HANDLER_MAP"


class TestWebhookBtnRouting:
    def test_route_telegram_btn_key_returns_none(self):
        from zavu_webhook import _route_telegram
        assert _route_telegram("btn:1") is None
        assert _route_telegram("btn:registrar:desaparecido") is None
        assert _route_telegram("btn:buscar:nombre") is None
        assert _route_telegram("btn:ayuda:como_usar") is None
