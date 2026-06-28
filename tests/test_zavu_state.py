import pytest
from zavu_state import ReportStateMachine, NOMBRE, CEDULA, UBICACION, FOTO, CONFIRMAR


class TestReportStateMachine:
    def setup_method(self):
        ReportStateMachine._states = {}

    def test_start_desaparecido(self):
        prompt = ReportStateMachine.start("chat1", "desaparecido")
        assert ReportStateMachine.is_active("chat1")
        assert ReportStateMachine.get_route("chat1") == "reportar:step:text"
        assert "desaparecido" in prompt.lower()

    def test_start_encontrado(self):
        prompt = ReportStateMachine.start("chat1", "encontrado")
        assert ReportStateMachine.is_active("chat1")
        assert "encontrado" in prompt.lower()

    def test_step_nombre_valid(self):
        ReportStateMachine.start("chat1", "desaparecido")
        resp = ReportStateMachine.handle_text("chat1", "Maria Perez")
        assert "cedula" in resp.lower()
        assert ReportStateMachine.get_route("chat1") == "reportar:step:text"

    def test_step_nombre_too_short(self):
        ReportStateMachine.start("chat1", "desaparecido")
        resp = ReportStateMachine.handle_text("chat1", "M")
        assert "al menos 2 caracteres" in resp.lower()
        assert ReportStateMachine.get_route("chat1") == "reportar:step:text"

    def test_step_cedula_valid(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        resp = ReportStateMachine.handle_text("chat1", "12345678")
        assert "ubicacion" in resp.lower()

    def test_step_cedula_non_numeric(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        resp = ReportStateMachine.handle_text("chat1", "abc")
        assert "solo numeros" in resp.lower()

    def test_step_cedula_skip(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        resp = ReportStateMachine.handle_text("chat1", "/skip")
        assert "ubicacion" in resp.lower()

    def test_step_ubicacion_valid(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        ReportStateMachine.handle_text("chat1", "12345")
        resp = ReportStateMachine.handle_text("chat1", "Caracas")
        assert "foto" in resp.lower()

    def test_step_ubicacion_skip(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        ReportStateMachine.handle_text("chat1", "12345")
        resp = ReportStateMachine.handle_text("chat1", "/skip")
        assert "foto" in resp.lower()

    def test_step_foto_skip(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        ReportStateMachine.handle_text("chat1", "12345")
        ReportStateMachine.handle_text("chat1", "Caracas")
        resp = ReportStateMachine.handle_text("chat1", "/skip")
        assert "resumen" in resp.lower() or "confirmar" in resp.lower()

    def test_step_foto_non_skip_text(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        ReportStateMachine.handle_text("chat1", "12345")
        ReportStateMachine.handle_text("chat1", "Caracas")
        resp = ReportStateMachine.handle_text("chat1", "blah")
        assert "foto" in resp.lower() and "skip" in resp.lower()

    def test_handle_photo_advances_to_confirmar(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        ReportStateMachine.handle_text("chat1", "12345")
        ReportStateMachine.handle_text("chat1", "Caracas")
        resp = ReportStateMachine.handle_photo("chat1", "https://example.com/photo.jpg")
        assert "resumen" in resp.lower() or "confirmar" in resp.lower()

    def test_handle_photo_wrong_step(self):
        ReportStateMachine.start("chat1", "desaparecido")
        resp = ReportStateMachine.handle_photo("chat1", "https://example.com/photo.jpg")
        assert resp is None

    def test_handle_photo_no_state(self):
        resp = ReportStateMachine.handle_photo("unknown", "https://example.com/photo.jpg")
        assert resp is None

    def test_step_confirmar_valid(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.Config.DB_PATH", tmp_path / "test.db")
        monkeypatch.setattr("config.Config.DATA_DIR", tmp_path)
        ReportStateMachine.start("chat1", "encontrado")
        ReportStateMachine.handle_text("chat1", "Pedro")
        ReportStateMachine.handle_text("chat1", "9999")
        ReportStateMachine.handle_text("chat1", "Caracas")
        ReportStateMachine.handle_text("chat1", "/skip")
        resp = ReportStateMachine.handle_text("chat1", "Confirmar")
        assert "guardado" in resp.lower()
        assert not ReportStateMachine.is_active("chat1")

    def test_confirmar_lowercase(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.Config.DB_PATH", tmp_path / "test.db")
        monkeypatch.setattr("config.Config.DATA_DIR", tmp_path)
        ReportStateMachine.start("chat1", "encontrado")
        ReportStateMachine.handle_text("chat1", "Pedro")
        ReportStateMachine.handle_text("chat1", "9999")
        ReportStateMachine.handle_text("chat1", "Caracas")
        ReportStateMachine.handle_text("chat1", "/skip")
        resp = ReportStateMachine.handle_text("chat1", "confirmar")
        assert "guardado" in resp.lower()

    def test_step_confirmar_invalid_text(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        ReportStateMachine.handle_text("chat1", "12345")
        ReportStateMachine.handle_text("chat1", "Caracas")
        ReportStateMachine.handle_text("chat1", "/skip")
        resp = ReportStateMachine.handle_text("chat1", "no se")
        assert "confirmar" in resp.lower()

    def test_cancel_clears_state(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        ReportStateMachine.handle_text("chat1", "/cancel")
        assert not ReportStateMachine.is_active("chat1")

    def test_start_clears_state(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        ReportStateMachine.handle_text("chat1", "/start")
        assert not ReportStateMachine.is_active("chat1")

    def test_cancelar_text_clears_state(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        ReportStateMachine.handle_text("chat1", "12345")
        ReportStateMachine.handle_text("chat1", "Caracas")
        ReportStateMachine.handle_text("chat1", "/skip")
        ReportStateMachine.handle_text("chat1", "Cancelar")
        assert not ReportStateMachine.is_active("chat1")

    def test_full_flow_desaparecido(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.Config.DB_PATH", tmp_path / "test.db")
        monkeypatch.setattr("config.Config.DATA_DIR", tmp_path)
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria Perez")
        ReportStateMachine.handle_text("chat1", "12345678")
        ReportStateMachine.handle_text("chat1", "Catia La Mar")
        ReportStateMachine.handle_text("chat1", "/skip")
        resp = ReportStateMachine.handle_text("chat1", "Confirmar")
        assert "guardado" in resp.lower()
        assert "Maria Perez" in resp
        assert "desaparecido" in resp.lower()

    def test_full_flow_encontrado(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.Config.DB_PATH", tmp_path / "test.db")
        monkeypatch.setattr("config.Config.DATA_DIR", tmp_path)
        ReportStateMachine.start("chat1", "encontrado")
        ReportStateMachine.handle_text("chat1", "Juan")
        ReportStateMachine.handle_text("chat1", "/skip")
        ReportStateMachine.handle_text("chat1", "/skip")
        ReportStateMachine.handle_text("chat1", "/skip")
        resp = ReportStateMachine.handle_text("chat1", "Confirmar")
        assert "guardado" in resp.lower()
        assert "encontrado" in resp.lower()

    def test_get_route_none(self):
        assert ReportStateMachine.get_route("unknown") is None

    def test_is_active_false(self):
        assert not ReportStateMachine.is_active("unknown")

    def test_foto_route(self):
        ReportStateMachine.start("chat1", "desaparecido")
        ReportStateMachine.handle_text("chat1", "Maria")
        ReportStateMachine.handle_text("chat1", "12345")
        ReportStateMachine.handle_text("chat1", "Caracas")
        assert ReportStateMachine.get_route("chat1") == "reportar:step:foto"
