import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture(autouse=True)
def reset_state():
    from zavu_state import ReportStateMachine
    ReportStateMachine._states = {}
    yield


def make_event(text="", message_type="text", button_id=None):
    event = {
        "id": "evt_test",
        "type": "message.inbound",
        "data": {
            "messageType": message_type,
            "text": text,
            "telegramChatId": "123456",
            "from": "123456",
            "channel": "telegram",
            "content": {},
        },
    }
    if button_id:
        event["data"]["content"]["interactiveReply"] = {"id": button_id}
    return event


class FakePeopleSearch:
    async def buscar(self, query):
        from services.people_search import PeopleSearchResult

        return [
            PeopleSearchResult(
                nombre="Test Person",
                fuente="ReportaVNZLA",
            )
        ]

    def formatear_resultado(self, result):
        return f"*{result.nombre}*\nFuente: {result.fuente}"


class TestZavuHandlers:
    def test_handle_start_cancels_state(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine
        ReportStateMachine.start("123456", "desaparecido")
        assert ReportStateMachine.is_active("123456")

        import asyncio
        from zavu_handlers import handle_start
        asyncio.run(handle_start(make_event(text="/start")))
        assert not ReportStateMachine.is_active("123456")

    def test_handle_menu_registrar_sets_waiting(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        import asyncio
        from zavu_handlers import handle_menu_registrar, _registrar_waiting

        asyncio.run(handle_menu_registrar(make_event(text="2")))
        assert _registrar_waiting.get("123456") is True

    def test_handle_refugios_sets_waiting(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        import asyncio
        from zavu_handlers import handle_refugios, _refugios_waiting

        asyncio.run(handle_refugios(make_event(text="/refugios")))
        assert _refugios_waiting.get("123456") is True

    def test_handle_refugios_with_city(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))

        async def mock_buscar_puntos(**kwargs):
            return [{"nombre": "Refugio X", "ciudad": "Caracas"}]

        monkeypatch.setattr("zavu_handlers.acopiove", MagicMock())
        from zavu_handlers import acopiove
        acopiove.buscar_puntos = mock_buscar_puntos

        import asyncio
        from zavu_handlers import handle_refugios
        asyncio.run(handle_refugios(make_event(text="/refugios Caracas")))

        assert any("Caracas" in s for s in sent)

    def test_handle_free_text_short(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))

        import asyncio
        from zavu_handlers import handle_free_text
        asyncio.run(handle_free_text(make_event(text="M")))

        assert any("2 caracteres" in s for s in sent)

    def test_handle_free_text_search(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        monkeypatch.setattr("zavu_handlers.people_search", FakePeopleSearch())

        import asyncio
        from zavu_handlers import handle_free_text
        asyncio.run(handle_free_text(make_event(text="Test")))

        assert any("Buscando" in s for s in sent)

    def test_handle_buscar_with_query(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        monkeypatch.setattr("zavu_handlers.people_search", FakePeopleSearch())

        import asyncio
        from zavu_handlers import handle_buscar
        asyncio.run(handle_buscar(make_event(text="/buscar Maria")))

        assert any("Buscando" in s for s in sent)

    def test_handle_buscar_without_query(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        import asyncio
        from zavu_handlers import handle_buscar
        asyncio.run(handle_buscar(make_event(text="/buscar")))
        assert any("nombre o cedula" in s for s in sent)

    def test_handle_photo_disabled(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        import asyncio
        from zavu_handlers import handle_photo
        asyncio.run(handle_photo(make_event(message_type="image")))
        assert any("no esta disponible" in s for s in sent)

    def test_handle_info(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        import asyncio
        from zavu_handlers import handle_info
        asyncio.run(handle_info(make_event(text="/info")))
        assert any("Fuentes" in s for s in sent)

    def test_handle_registrar_cmd_desaparecido(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine

        import asyncio
        from zavu_handlers import handle_registrar_cmd
        asyncio.run(handle_registrar_cmd(make_event(text="/registrar desaparecido")))

        assert ReportStateMachine.is_active("123456")

    def test_handle_registrar_cmd_encontrado(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine

        import asyncio
        from zavu_handlers import handle_registrar_cmd
        asyncio.run(handle_registrar_cmd(make_event(text="/registrar encontrado")))

        assert ReportStateMachine.is_active("123456")

    def test_handle_reportar_text_continues_flow(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine
        ReportStateMachine.start("123456", "desaparecido")

        import asyncio
        from zavu_handlers import handle_reportar_text
        asyncio.run(handle_reportar_text(make_event(text="Maria Perez")))

        assert ReportStateMachine.is_active("123456")

    def test_handle_reportar_text_cancel(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine
        ReportStateMachine.start("123456", "desaparecido")

        import asyncio
        from zavu_handlers import handle_reportar_text
        asyncio.run(handle_reportar_text(make_event(text="/cancel")))

        assert not ReportStateMachine.is_active("123456")

    def test_handle_reportar_photo_no_url(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))

        import asyncio
        from zavu_handlers import handle_reportar_photo
        asyncio.run(handle_reportar_photo(make_event(message_type="image")))

        assert any("No se pudo obtener" in s for s in sent)

    def test_handle_reportar_photo_with_url(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        from zavu_state import ReportStateMachine
        ReportStateMachine.start("123456", "desaparecido")
        # Advance to FOTO step
        ReportStateMachine.handle_text("123456", "Test Person")
        ReportStateMachine.handle_text("123456", "12345678")
        ReportStateMachine.handle_text("123456", "Caracas")

        event = make_event(message_type="image")
        event["data"]["content"] = {"mediaUrl": "https://example.com/foto.jpg"}

        import asyncio
        from zavu_handlers import handle_reportar_photo
        asyncio.run(handle_reportar_photo(event))

        assert any("Resumen" in s for s in sent)
        assert ReportStateMachine.is_active("123456")
        assert ReportStateMachine._states["123456"]["step"] == "reportar:step:confirmar"
