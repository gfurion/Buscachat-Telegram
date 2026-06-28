import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.reportavnzla_api import ReportaVNZLAAPI


@pytest.fixture
def api():
    return ReportaVNZLAAPI()


@pytest.mark.asyncio
async def test_buscar_personas_returns_results(api):
    mock_data = {
        "data": [
            {
                "nombre": "Maria", "apellido": "Gonzalez", "cedula": "V-12345678",
                "edad": 35, "genero": "femenino", "estado": "buscado",
                "ultimaUbicacion": "La Guaira",
            },
        ]
    }
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_data)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    with patch("services.reportavnzla_api.aiohttp.ClientSession") as mock_session:
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_resp)

        results = await api.buscar_personas(query="Maria")
        assert len(results) == 1
        assert results[0]["nombre"] == "Maria"


@pytest.mark.asyncio
async def test_buscar_personas_empty_on_no_query(api):
    results = await api.buscar_personas(query="", cedula=None)
    assert results == []


@pytest.mark.asyncio
async def test_buscar_personas_empty_on_error(api):
    mock_resp = AsyncMock()
    mock_resp.status = 500
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    with patch("services.reportavnzla_api.aiohttp.ClientSession") as mock_session:
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_resp)

        results = await api.buscar_personas(query="Maria")
        assert results == []


@pytest.mark.asyncio
async def test_buscar_por_cedula_returns_results(api):
    mock_data = {
        "data": [
            {"nombre": "Juan", "apellido": "Perez", "cedula": "V-12345678", "estado": "buscado"},
        ]
    }
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_data)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    with patch("services.reportavnzla_api.aiohttp.ClientSession") as mock_session:
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_resp)

        results = await api.buscar_por_cedula("12345678")
        assert len(results) == 1
        assert results[0]["cedula"] == "V-12345678"


def test_formatear_persona(api):
    persona = {
        "nombre": "Maria", "apellido": "Gonzalez", "cedula": "V-12345678",
        "edad": 35, "estado": "buscado", "ultimaUbicacion": "La Guaira",
    }
    result = api.formatear_persona(persona)
    assert "Maria Gonzalez" in result
    assert "V-12345678" in result
    assert "La Guaira" in result
    assert "buscado" in result


def test_formatear_persona_encontrado(api):
    persona = {
        "nombre": "Pedro", "apellido": "Perez", "estado": "encontrado",
    }
    result = api.formatear_persona(persona)
    assert "Pedro Perez" in result
    assert "encontrado" in result
