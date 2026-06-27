import pytest
from services.database import Database
from models.persona import Persona, TipoReporte


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr("config.Config.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("config.Config.DATA_DIR", tmp_path)
    return Database()


def test_guardar_y_buscar_por_nombre(db):
    persona = Persona(
        nombre="Maria Perez",
        cedula="12345678",
        tipo=TipoReporte.DESAPARECIDO,
        reporter_chat_id=123,
    )
    persona_id = db.guardar_persona(persona)
    assert persona_id is not None

    resultados = db.buscar_por_nombre("Maria")
    assert len(resultados) == 1
    assert resultados[0].nombre == "Maria Perez"


def test_guardar_y_buscar_por_cedula(db):
    persona = Persona(
        nombre="Juan Lopez",
        cedula="87654321",
        tipo=TipoReporte.ENCONTRADO,
        reporter_chat_id=456,
    )
    db.guardar_persona(persona)

    resultados = db.buscar_por_cedula("87654321")
    assert len(resultados) == 1
    assert resultados[0].cedula == "87654321"


def test_contar_por_tipo(db):
    db.guardar_persona(Persona(
        nombre="A", tipo=TipoReporte.DESAPARECIDO, reporter_chat_id=1
    ))
    db.guardar_persona(Persona(
        nombre="B", tipo=TipoReporte.DESAPARECIDO, reporter_chat_id=1
    ))
    db.guardar_persona(Persona(
        nombre="C", tipo=TipoReporte.ENCONTRADO, reporter_chat_id=1
    ))

    conteo = db.contar_por_tipo()
    assert conteo["desaparecido"] == 2
    assert conteo["encontrado"] == 1


def test_buscar_por_texto(db):
    db.guardar_persona(Persona(
        nombre="Pedro Gomez",
        cedula="11111111",
        ubicacion="Maracay",
        tipo=TipoReporte.DESAPARECIDO,
        reporter_chat_id=1,
    ))

    resultados = db.buscar_por_texto("Maracay")
    assert len(resultados) == 1
    assert resultados[0].nombre == "Pedro Gomez"
