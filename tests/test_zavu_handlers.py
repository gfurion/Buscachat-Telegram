import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture(autouse=True)
def reset_state():
    from zavu_state import ReportStateMachine
    from zavu_handlers import _registrar_waiting, _refugios_waiting
    ReportStateMachine._states = {}
    _registrar_waiting.clear()
    _refugios_waiting.clear()
    yield


CHAT_ID = "123456"


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
        ReportStateMachine.start(CHAT_ID, "desaparecido")
        assert ReportStateMachine.is_active(CHAT_ID)

        import asyncio
        from zavu_handlers import handle_start
        asyncio.run(handle_start(CHAT_ID, "/start"))
        assert not ReportStateMachine.is_active(CHAT_ID)

    def test_handle_menu_registrar_sets_waiting(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        import asyncio
        from zavu_handlers import handle_menu_registrar, _registrar_waiting

        asyncio.run(handle_menu_registrar(CHAT_ID, "2"))
        assert _registrar_waiting.get(CHAT_ID) is True

    def test_handle_refugios_sets_waiting(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        import asyncio
        from zavu_handlers import handle_refugios, _refugios_waiting

        asyncio.run(handle_refugios(CHAT_ID, "/refugios"))
        assert _refugios_waiting.get(CHAT_ID) is True

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
        asyncio.run(handle_refugios(CHAT_ID, "/refugios Caracas"))

        assert any("Caracas" in s for s in sent)

    def test_handle_free_text_short(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))

        import asyncio
        from zavu_handlers import handle_free_text
        asyncio.run(handle_free_text(CHAT_ID, "M"))

        assert any("2 caracteres" in s for s in sent)

    def test_handle_free_text_search(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        monkeypatch.setattr("zavu_handlers.people_search", FakePeopleSearch())

        import asyncio
        from zavu_handlers import handle_free_text
        asyncio.run(handle_free_text(CHAT_ID, "Test"))

        assert any("Buscando" in s for s in sent)

    def test_handle_buscar_with_query(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        monkeypatch.setattr("zavu_handlers.people_search", FakePeopleSearch())

        import asyncio
        from zavu_handlers import handle_buscar
        asyncio.run(handle_buscar(CHAT_ID, "/buscar Maria"))

        assert any("Buscando" in s for s in sent)

    def test_handle_buscar_without_query(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        import asyncio
        from zavu_handlers import handle_buscar
        asyncio.run(handle_buscar(CHAT_ID, "/buscar"))
        assert any("nombre o cedula" in s for s in sent)

    def test_handle_photo_disabled(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        import asyncio
        from zavu_handlers import handle_photo
        asyncio.run(handle_photo(CHAT_ID, ""))
        assert any("no esta disponible" in s for s in sent)

    def test_handle_info(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        import asyncio
        from zavu_handlers import handle_info
        asyncio.run(handle_info(CHAT_ID, "/info"))
        assert any("Fuentes" in s for s in sent)

    def test_handle_registrar_cmd_desaparecido(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine

        import asyncio
        from zavu_handlers import handle_registrar_cmd
        asyncio.run(handle_registrar_cmd(CHAT_ID, "/registrar desaparecido"))

        assert ReportStateMachine.is_active(CHAT_ID)

    def test_handle_registrar_cmd_encontrado(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine

        import asyncio
        from zavu_handlers import handle_registrar_cmd
        asyncio.run(handle_registrar_cmd(CHAT_ID, "/registrar encontrado"))

        assert ReportStateMachine.is_active(CHAT_ID)

    def test_handle_reportar_text_continues_flow(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine
        ReportStateMachine.start(CHAT_ID, "desaparecido")

        import asyncio
        from zavu_handlers import handle_reportar_text
        asyncio.run(handle_reportar_text(CHAT_ID, "Maria Perez"))

        assert ReportStateMachine.is_active(CHAT_ID)

    def test_handle_reportar_text_cancel(self, monkeypatch):
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: None)
        from zavu_state import ReportStateMachine
        ReportStateMachine.start(CHAT_ID, "desaparecido")

        import asyncio
        from zavu_handlers import handle_reportar_text
        asyncio.run(handle_reportar_text(CHAT_ID, "/cancel"))

        assert not ReportStateMachine.is_active(CHAT_ID)

    def test_handle_photo_report_empty_file_id(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        import asyncio
        from zavu_handlers import handle_photo_report
        asyncio.run(handle_photo_report(CHAT_ID, ""))
        assert any("No se recibió" in s for s in sent) or any("foto" in s for s in sent)

    def test_handle_photo_report_no_active_state(self, monkeypatch):
        sent = []
        monkeypatch.setattr("zavu_handlers.send_text", lambda to, text: sent.append(text))
        import asyncio
        from zavu_handlers import handle_photo_report
        asyncio.run(handle_photo_report(CHAT_ID, "file_id_123"))
        assert any("Error" in s for s in sent) or any("foto" in s for s in sent)

    def test_handler_map_has_photo_report(self):
        from zavu_handlers import HANDLER_MAP
        assert "photo:report" in HANDLER_MAP
