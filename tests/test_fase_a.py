import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestTelegramClient:
    def test_import(self):
        from telegram_client import send_text, send_photo, answer_callback
        assert callable(send_text)
        assert callable(send_photo)
        assert callable(answer_callback)

    @patch("telegram_client.get_bot")
    def test_send_text_calls_bot(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import send_text
        send_text(123456, "Hello")

        mock_bot.send_message.assert_called_once()

    @patch("telegram_client.get_bot")
    def test_send_photo_calls_bot(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.send_photo = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import send_photo
        send_photo(123456, "https://example.com/photo.jpg", "caption")

        mock_bot.send_photo.assert_called_once()

    @patch("telegram_client.get_bot")
    def test_answer_callback_calls_bot(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_bot.answer_callback_query = AsyncMock()
        mock_get_bot.return_value = mock_bot

        from telegram_client import answer_callback
        answer_callback("cb_id_123", "done")

        mock_bot.answer_callback_query.assert_called_once()


class TestConfigFlag:
    def test_telegram_enabled_default_false(self):
        from config import Config
        assert Config.TELEGRAM_ENABLED is False

    def test_telegram_enabled_can_be_true(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_ENABLED", "true")
        import importlib
        import config as config_module
        importlib.reload(config_module)
        assert config_module.Config.TELEGRAM_ENABLED is True
        monkeypatch.delenv("TELEGRAM_ENABLED")
        importlib.reload(config_module)


class TestStatePersistence:
    def test_save_and_load(self):
        from services.database import get_db
        db = get_db()
        db.save_conversation_state("test_chat", '{"step": "test"}')
        result = db.load_conversation_state("test_chat")
        assert result == '{"step": "test"}'
        db.delete_conversation_state("test_chat")
        assert db.load_conversation_state("test_chat") is None

    def test_state_persists_across_instances(self):
        from services.database import Database
        db1 = Database()
        db1.save_conversation_state("persist_test", '{"step": "nombre"}')
        db2 = Database()
        result = db2.load_conversation_state("persist_test")
        assert result == '{"step": "nombre"}'
        db1.delete_conversation_state("persist_test")


class TestTelegramWebhook:
    def test_import(self):
        from telegram_webhook import app
        assert app is not None

    def test_health(self):
        from fastapi.testclient import TestClient
        from telegram_webhook import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_verify_telegram_secret_valid(self):
        from telegram_webhook import _verify_telegram_secret
        from config import Config
        Config.TELEGRAM_WEBHOOK_SECRET = "test_secret"
        assert _verify_telegram_secret("test_secret") is True
        assert _verify_telegram_secret("wrong") is False

    def test_verify_telegram_secret_skip(self):
        from telegram_webhook import _verify_telegram_secret
        from config import Config
        Config.TELEGRAM_WEBHOOK_SECRET = "change-me"
        assert _verify_telegram_secret("anything") is True

    def test_route_telegram_commands(self):
        from telegram_webhook import _route_telegram
        assert _route_telegram("/start") == "start"
        assert _route_telegram("/buscar Maria") == "buscar"
        assert _route_telegram("/ayuda") == "ayuda"
        assert _route_telegram("/info") == "info"
        assert _route_telegram("/registrar encontrado") == "registrar_cmd"
        assert _route_telegram("/emergencia") == "emergencia"
        assert _route_telegram("/refugios") == "refugios"
        assert _route_telegram("/unknown") is None

    def test_route_telegram_menu(self):
        from telegram_webhook import _route_telegram
        assert _route_telegram("1") == "menu:buscar"
        assert _route_telegram("2") == "menu:registrar"
        assert _route_telegram("3") == "menu:refugios"
        assert _route_telegram("4") == "menu:emergencia"
        assert _route_telegram("5") == "ayuda"

    def test_route_telegram_free_text(self):
        from telegram_webhook import _route_telegram
        assert _route_telegram("Maria Perez") == "free_text"
        assert _route_telegram("M") is None
