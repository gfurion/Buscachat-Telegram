import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.acopiove_api import AcopioVEAPI
from services.found_people_api import FoundPeopleAPI
from services.normalizer import normalizar_texto

logger = logging.getLogger(__name__)


@dataclass
class PeopleSearchResult:
    nombre: str
    fuente: str
    cedula: str = ""
    estado: str = ""
    ubicacion: str = ""
    info: str = ""
    source_url: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


class PeopleSearchAggregator:
    def __init__(
        self,
        found_people: Optional[FoundPeopleAPI] = None,
        acopiove: Optional[AcopioVEAPI] = None,
    ):
        self.found_people = found_people or FoundPeopleAPI()
        self.acopiove = acopiove or AcopioVEAPI()

    async def buscar(self, query: str) -> List[PeopleSearchResult]:
        if not query or len(query.strip()) < 2:
            return []

        responses = await asyncio.gather(
            self._buscar_found_people(query),
            self._buscar_acopiove(query),
            return_exceptions=True,
        )

        results: List[PeopleSearchResult] = []
        for response in responses:
            if isinstance(response, Exception):
                logger.error(f"People search source failed: {response}")
                continue
            results.extend(response)

        return self._deduplicate(results)

    async def _buscar_found_people(self, query: str) -> List[PeopleSearchResult]:
        rows = await self.found_people.buscar(query)
        return [self._from_found_people(row) for row in rows]

    async def _buscar_acopiove(self, query: str) -> List[PeopleSearchResult]:
        rows = await self.acopiove.buscar_personas(query)
        return [self._from_acopiove(row) for row in rows]

    def _from_found_people(self, row: Dict[str, Any]) -> PeopleSearchResult:
        return PeopleSearchResult(
            nombre=self._first(row, "fullName", "name", default="Sin nombre"),
            cedula=self._first(row, "documentId", "cedula"),
            estado=self._humanize_status(self._first(row, "status", default="reportado")),
            ubicacion=self._first(row, "location", "ubicacion", "place"),
            info=self._first(row, "relevantInfo", "info", "description"),
            fuente="found-people-ve-bot",
            source_url=self._first(row, "sourceUrl", "url"),
            raw=row,
        )

    def _from_acopiove(self, row: Dict[str, Any]) -> PeopleSearchResult:
        return PeopleSearchResult(
            nombre=self._first(row, "nombre", "fullName", "nombreCompleto", default="Sin nombre"),
            cedula=self._first(row, "cedula", "documentId", "documento"),
            estado=self._humanize_status(self._first(row, "estado", "status", "condicion")),
            ubicacion=self._first(row, "ubicacion_general", "ubicacion", "lugarNombre", "direccion"),
            info=self._first(row, "observaciones", "relevantInfo", "info", "descripcion"),
            fuente=self._first(row, "fuente", default="AcopioVE"),
            source_url=self._first(row, "sourceUrl", "url"),
            raw=row,
        )

    def _deduplicate(self, results: List[PeopleSearchResult]) -> List[PeopleSearchResult]:
        deduped: Dict[str, PeopleSearchResult] = {}
        order: List[str] = []

        for result in results:
            key = self._dedupe_key(result)
            if key not in deduped:
                deduped[key] = result
                order.append(key)
                continue

            if self._quality_score(result) > self._quality_score(deduped[key]):
                deduped[key] = result

        return [deduped[key] for key in order]

    def _dedupe_key(self, result: PeopleSearchResult) -> str:
        cedula = self._normalize_cedula(result.cedula)
        if cedula:
            return f"cedula:{cedula}"

        nombre = normalizar_texto(result.nombre)
        ubicacion = normalizar_texto(result.ubicacion)
        if nombre and ubicacion:
            return f"persona:{nombre}:{ubicacion}"

        raw_id = result.raw.get("id") or result.raw.get("slug") or result.nombre
        return f"source:{result.fuente}:{raw_id}"

    def _quality_score(self, result: PeopleSearchResult) -> int:
        fields = (result.cedula, result.estado, result.ubicacion, result.info, result.source_url)
        return sum(1 for value in fields if value)

    def formatear_resultado(self, result: PeopleSearchResult) -> str:
        partes = [f"*{result.nombre}*"]
        if result.estado:
            partes.append(f"Estado: {result.estado}")
        if result.cedula:
            partes.append(f"Cedula: {result.cedula}")
        if result.ubicacion:
            partes.append(f"Ubicacion: {result.ubicacion}")
        if result.info:
            partes.append(f"Info: {result.info[:200]}")
        partes.append(f"Fuente: {result.fuente}")
        if result.source_url:
            partes.append(f"URL: {result.source_url}")
        return "\n".join(partes)

    def _normalize_cedula(self, cedula: str) -> str:
        if not cedula or "*" in cedula:
            return ""
        digits = re.sub(r"\D", "", cedula)
        return digits if len(digits) >= 5 else ""

    def _humanize_status(self, status: str) -> str:
        if not status:
            return ""
        return status.replace("_", " ").strip()

    def _first(self, row: Dict[str, Any], *keys: str, default: str = "") -> str:
        for key in keys:
            value = row.get(key)
            if value is not None and value != "":
                return str(value)
        return default

    def _join_non_empty(self, *values: str) -> str:
        return " · ".join(value for value in values if value)
