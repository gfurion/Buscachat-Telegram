import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.acopiove_api import AcopioVEAPI


@pytest.fixture
def api():
    return AcopioVEAPI()


@pytest.mark.asyncio
async def test_buscar_puntos_returns_results(api):
    mock_data = {
        "data": [
            {"nombre": "Refugio Plaza Bolivar", "ciudad": "Caracas", "recibe": ["agua", "alimentos"]},
        ]
    }
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_data)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    with patch("services.acopiove_api.aiohttp.ClientSession") as mock_session:
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_resp)

        results = await api.buscar_puntos(tipo="refugio", ciudad="Caracas")
        assert len(results) == 1
        assert results[0]["nombre"] == "Refugio Plaza Bolivar"


@pytest.mark.asyncio
async def test_buscar_telefonos_returns_results(api):
    mock_data = {
        "data": [
            {"nombre": "Proteccion Civil", "telefono": "171", "ciudad": "Caracas"},
        ]
    }
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_data)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    with patch("services.acopiove_api.aiohttp.ClientSession") as mock_session:
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_resp)

        results = await api.buscar_telefonos()
        assert len(results) == 1
        assert results[0]["nombre"] == "Proteccion Civil"


def test_formatear_punto(api):
    punto = {"nombre": "Refugio Plaza", "ciudad": "Caracas", "recibe": ["agua"]}
    result = api.formatear_punto(punto)
    assert "Refugio Plaza" in result
    assert "Caracas" in result


def test_formatear_telefono(api):
    tel = {"nombre": "Proteccion Civil", "telefono": "171", "ciudad": "Caracas"}
    result = api.formatear_telefono(tel)
    assert "Proteccion Civil" in result
    assert "171" in result
