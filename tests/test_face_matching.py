import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from services.face_matching import FaceMatcher
from models.persona import Persona, TipoReporte


@pytest.fixture
def face_matcher(tmp_path, monkeypatch):
    monkeypatch.setattr("config.Config.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("config.Config.DATA_DIR", tmp_path)
    monkeypatch.setattr("config.Config.FACE_MATCH_THRESHOLD", 0.40)
    return FaceMatcher()


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr("config.Config.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("config.Config.DATA_DIR", tmp_path)
    from services.database import Database
    return Database()


def test_store_and_search(face_matcher, db):
    persona = Persona(
        nombre="Test Person",
        tipo=TipoReporte.DESAPARECIDO,
        reporter_chat_id=1,
    )
    persona_id = db.guardar_persona(persona)

    embedding = np.random.rand(512).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    db.guardar_embedding(persona_id, embedding)

    probe = embedding + np.random.rand(512).astype(np.float32) * 0.01
    probe = probe / np.linalg.norm(probe)

    results = db.buscar_por_facial(probe)
    assert len(results) > 0
    assert results[0][0].nombre == "Test Person"


def test_threshold_filters(tmp_path, monkeypatch):
    monkeypatch.setattr("config.Config.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("config.Config.DATA_DIR", tmp_path)
    monkeypatch.setattr("config.Config.FACE_MATCH_THRESHOLD", 0.99)

    from services.database import Database
    db = Database()

    persona = Persona(
        nombre="Test Person",
        tipo=TipoReporte.DESAPARECIDO,
        reporter_chat_id=1,
    )
    persona_id = db.guardar_persona(persona)

    embedding = np.random.rand(512).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    db.guardar_embedding(persona_id, embedding)

    probe = np.random.rand(512).astype(np.float32)
    probe = probe / np.linalg.norm(probe)

    results = db.buscar_por_facial(probe, top_k=10)
    assert len(results) == 0


def test_extract_embedding_disabled():
    face_matcher = FaceMatcher()
    face_matcher.enabled = False
    result = face_matcher.extract_embedding(b"fake image")
    assert result is None
