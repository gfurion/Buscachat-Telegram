import pytest

from services.people_search import PeopleSearchAggregator


class FakeClient:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error

    async def buscar(self, query):
        if self.error:
            raise self.error
        return self.results


class FakeAcopioClient:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error

    async def buscar_personas(self, query):
        if self.error:
            raise self.error
        return self.results


@pytest.mark.asyncio
async def test_buscar_normalizes_and_merges_sources():
    search = PeopleSearchAggregator(
        found_people=FakeClient([
            {
                "fullName": "Maria Perez",
                "documentId": "12345678",
                "relevantInfo": "Hospital Central",
                "sourceUrl": "https://example.com/maria",
            }
        ]),
        acopiove=FakeAcopioClient([
            {
                "nombre": "Juan Lopez",
                "estado": "localizado",
                "ubicacion_general": "Hospital Vargas",
                "fuente": "AcopioVE",
            }
        ]),
    )

    results = await search.buscar("Maria")

    assert len(results) == 2
    assert results[0].nombre == "Maria Perez"
    assert results[0].cedula == "12345678"
    assert results[1].fuente == "AcopioVE"
    assert results[1].ubicacion == "Hospital Vargas"


@pytest.mark.asyncio
async def test_buscar_continues_when_a_source_fails():
    search = PeopleSearchAggregator(
        found_people=FakeClient([
            {"fullName": "Maria Perez", "documentId": "12345678"}
        ]),
        acopiove=FakeAcopioClient(error=RuntimeError("timeout")),
    )

    results = await search.buscar("Maria")

    assert len(results) == 1
    assert results[0].nombre == "Maria Perez"


@pytest.mark.asyncio
async def test_buscar_deduplicates_by_cedula():
    search = PeopleSearchAggregator(
        found_people=FakeClient([
            {
                "fullName": "Maria Perez",
                "documentId": "12345678",
            }
        ]),
        acopiove=FakeAcopioClient([
            {
                "nombre": "Maria P.",
                "cedula": "V-12345678",
                "ubicacion_general": "La Guaira",
                "estado": "localizado",
                "fuente": "AcopioVE",
            }
        ]),
    )

    results = await search.buscar("Maria")

    assert len(results) == 1
    assert results[0].nombre == "Maria P."
    assert results[0].ubicacion == "La Guaira"


def test_formatear_resultado_includes_source():
    search = PeopleSearchAggregator(
        found_people=FakeClient([]),
        acopiove=FakeAcopioClient([]),
    )
    result = search._from_found_people({
        "fullName": "Juan Lopez",
        "documentId": "87654321",
        "sourceUrl": "https://example.com",
    })

    formatted = search.formatear_resultado(result)

    assert "Juan Lopez" in formatted
    assert "87654321" in formatted
    assert "found-people-ve-bot" in formatted
