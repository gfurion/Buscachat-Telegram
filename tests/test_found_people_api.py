import pytest
import aiohttp
from unittest.mock import AsyncMock, patch
from services.found_people_api import FoundPeopleAPI


@pytest.fixture
def api():
    return FoundPeopleAPI()


@pytest.mark.asyncio
async def test_buscar_returns_results(api):
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "data": [
            {
                "fullName": "Maria Perez",
                "documentId": "12345678",
                "relevantInfo": "Hospital Central",
                "sourceUrl": "https://example.com",
            },
        ],
        "pagination": {"total": 1},
    })
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        resultados = await api.buscar("Maria")
        assert len(resultados) == 1
        assert resultados[0]["fullName"] == "Maria Perez"


@pytest.mark.asyncio
async def test_buscar_returns_empty_on_error(api):
    with patch(
        "aiohttp.ClientSession.get",
        side_effect=aiohttp.ClientError("timeout"),
    ):
        resultados = await api.buscar("Maria")
        assert resultados == []


def test_formatear_resultado(api):
    persona = {
        "fullName": "Juan Lopez",
        "documentId": "87654321",
        "relevantInfo": "Hospital General",
        "sourceUrl": "https://example.com",
    }
    resultado = api.formatear_resultado(persona)
    assert "Juan Lopez" in resultado
    assert "87654321" in resultado
