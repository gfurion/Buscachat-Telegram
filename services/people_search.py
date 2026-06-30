import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.acopiove_api import AcopioVEAPI
from services.database import get_db
from services.found_people_api import FoundPeopleAPI
from services.normalizer import normalizar_texto, escape_md
from services.reportavnzla_api import ReportaVNZLAAPI
from services.venezuela_te_busca_api import VenezuelaTeBuscaAPI

logger = logging.getLogger(__name__)


@dataclass
class PeopleSearchResult:
    nombre: str
    fuente: str
    cedula: str = ""
    estado: str = ""
    ubicacion: str = ""
    info: str = ""
    foto_path: str = ""
    source_url: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


class PeopleSearchAggregator:
    def __init__(
        self,
        found_people: Optional[FoundPeopleAPI] = None,
        acopiove: Optional[AcopioVEAPI] = None,
        reportavnzla: Optional[ReportaVNZLAAPI] = None,
        venezuela_te_busca: Optional[VenezuelaTeBuscaAPI] = None,
        db: Optional["Database"] = None,
    ):
        self.found_people = found_people or FoundPeopleAPI()
        self.acopiove = acopiove or AcopioVEAPI()
        self.reportavnzla = reportavnzla or ReportaVNZLAAPI()
        self.venezuela_te_busca = venezuela_te_busca
        self.db = db

    async def buscar(self, query: str) -> List[PeopleSearchResult]:
        if not query or len(query.strip()) < 2:
            return []

        tasks = [
            self._buscar_reportavnzla(query),
            self._buscar_found_people(query),
            self._buscar_acopiove(query),
        ]
        if self.venezuela_te_busca is not None:
            tasks.append(self._buscar_venezuela_te_busca(query))
        if self.db is not None:
            tasks.append(self._buscar_local_db(query))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        results: List[PeopleSearchResult] = []
        for response in responses:
            if isinstance(response, Exception):
                logger.error(f"People search source failed: {response}")
                continue
            results.extend(response)

        return self._deduplicate(results)

    async def _buscar_reportavnzla(self, query: str) -> List[PeopleSearchResult]:
        rows = await self.reportavnzla.buscar_personas(query=query)
        return [self._from_reportavnzla(row) for row in rows]

    async def _buscar_found_people(self, query: str) -> List[PeopleSearchResult]:
        rows = await self.found_people.buscar(query)
        return [self._from_found_people(row) for row in rows]

    async def _buscar_acopiove(self, query: str) -> List[PeopleSearchResult]:
        rows = await self.acopiove.buscar_personas(query)
        return [self._from_acopiove(row) for row in rows]

    async def _buscar_venezuela_te_busca(self, query: str) -> List[PeopleSearchResult]:
        rows = await self.venezuela_te_busca.buscar(query)
        return [self._from_venezuela_te_busca(row) for row in rows]

    async def _buscar_local_db(self, query: str) -> List[PeopleSearchResult]:
        try:
            rows = await asyncio.to_thread(self.db.buscar_por_texto, query)
            return [self._from_local_db(row) for row in rows]
        except Exception as e:
            logger.error(f"Local DB search failed: {e}")
            return []

    def _from_local_db(self, persona: "Persona") -> PeopleSearchResult:
        return PeopleSearchResult(
            nombre=persona.nombre,
            cedula=persona.cedula,
            estado="reportado",
            ubicacion=persona.ubicacion,
            info=persona.descripcion,
            foto_path=persona.foto_path or "",
            fuente="BuscaChat (local)",
            raw={"id": persona.id, "tipo": persona.tipo.value if persona.tipo else ""},
        )

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

    def _from_reportavnzla(self, row: Dict[str, Any]) -> PeopleSearchResult:
        nombre = self._join_name_parts(
            self._first(row, "nombre"),
            self._first(row, "apellido"),
        ) or self._first(row, "fullName", "name", default="Sin nombre")
        info = self._join_non_empty(
            self._format_age(row.get("edad")),
            self._first(row, "descripcion", "observaciones", "info"),
        )
        return PeopleSearchResult(
            nombre=nombre,
            cedula=self._first(row, "cedula", "documentId", "documento"),
            estado=self._humanize_status(self._first(row, "estado", "status", "condicion")),
            ubicacion=self._first(row, "ultimaUbicacion", "ubicacion", "ubicacion_general", "lugarNombre"),
            info=info,
            fuente="ReportaVNZLA",
            source_url=self._first(row, "sourceUrl", "url", "fotoUrl"),
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

    def _from_venezuela_te_busca(self, row: Dict[str, Any]) -> PeopleSearchResult:
        return PeopleSearchResult(
            nombre=row.get("nombre", "Sin nombre"),
            cedula=row.get("cedula", ""),
            estado=row.get("estado", ""),
            ubicacion=row.get("ubicacion", ""),
            info=row.get("info", ""),
            foto_path=row.get("foto_path", ""),
            fuente="VenezuelaTeBusca",
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
        nombre = escape_md(result.nombre)
        estado = escape_md(result.estado) if result.estado else ""
        ubicacion = escape_md(result.ubicacion) if result.ubicacion else ""
        info = escape_md(result.info[:200]) if result.info else ""
        fuente = escape_md(result.fuente) if result.fuente else ""

        partes = [f"*{nombre}*"]
        if estado:
            partes.append(f"Estado: {estado}")
        if result.cedula:
            partes.append(f"Cedula: {result.cedula}")
        if ubicacion:
            partes.append(f"Ubicacion: {ubicacion}")
        if info:
            partes.append(f"Info: {info}")
        if result.foto_path:
            partes.append("Foto: disponible")
        partes.append(f"Fuente: {fuente}")
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

    def _join_name_parts(self, *values: str) -> str:
        return " ".join(value for value in values if value)

    def _format_age(self, age: Any) -> str:
        if age is None or age == "":
            return ""
        return f"Edad: {age}"
