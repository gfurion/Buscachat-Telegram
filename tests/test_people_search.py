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


class FakeReportaClient:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error

    async def buscar_personas(self, query="", **kwargs):
        if self.error:
            raise self.error
        return self.results


@pytest.mark.asyncio
async def test_buscar_normalizes_and_merges_sources():
    search = PeopleSearchAggregator(
        reportavnzla=FakeReportaClient([
            {
                "nombre": "Ana",
                "apellido": "Torres",
                "cedula": "V-87654321",
                "estado": "buscado",
                "ultimaUbicacion": "La Guaira",
                "edad": 30,
            }
        ]),
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

    assert len(results) == 3
    assert results[0].nombre == "Ana Torres"
    assert results[0].cedula == "V-87654321"
    assert results[0].fuente == "ReportaVNZLA"
    assert results[1].nombre == "Maria Perez"
    assert results[2].fuente == "AcopioVE"
    assert results[2].ubicacion == "Hospital Vargas"


@pytest.mark.asyncio
async def test_buscar_continues_when_a_source_fails():
    search = PeopleSearchAggregator(
        reportavnzla=FakeReportaClient(error=RuntimeError("timeout")),
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
        reportavnzla=FakeReportaClient([]),
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
        reportavnzla=FakeReportaClient([]),
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


def test_from_reportavnzla_normalizes_result():
    search = PeopleSearchAggregator(
        reportavnzla=FakeReportaClient([]),
        found_people=FakeClient([]),
        acopiove=FakeAcopioClient([]),
    )

    result = search._from_reportavnzla({
        "nombre": "Maria",
        "apellido": "Gonzalez",
        "cedula": "V-12345678",
        "estado": "buscado",
        "ultimaUbicacion": "La Guaira",
        "edad": 35,
    })

    assert result.nombre == "Maria Gonzalez"
    assert result.fuente == "ReportaVNZLA"
    assert result.ubicacion == "La Guaira"
    assert "Edad: 35" in result.info
