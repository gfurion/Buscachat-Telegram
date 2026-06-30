import asyncio
import logging
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://venezuelatebusca.com"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}


def _decode_flattened_response(data: Any) -> Any:
    if not isinstance(data, list) or not data:
        return data

    resolved: dict[int, Any] = {}

    def walk(index: int) -> Any:
        if index < 0:
            return None
        if index in resolved:
            return resolved[index]

        item = data[index]
        if item is None or not isinstance(item, dict | list):
            return item

        if isinstance(item, list):
            items: list[Any] = []
            resolved[index] = items
            items.extend(walk(value_index) for value_index in item)
            return items

        obj: dict[str, Any] = {}
        resolved[index] = obj
        for pointer_key, value_index in item.items():
            if not pointer_key.startswith("_"):
                continue
            actual_key = walk(int(pointer_key[1:]))
            if actual_key is not None:
                obj[str(actual_key)] = walk(value_index)
        return obj

    return walk(0)


def _extract_persons(decoded: dict) -> List[Dict]:
    if not isinstance(decoded, dict):
        logger.warning("VenezuelaTeBusca: decoded response is not a dict")
        return []

    route = decoded.get("routes/_index")
    if not isinstance(route, dict) or not isinstance(route.get("data"), dict):
        logger.warning("VenezuelaTeBusca: missing routes/_index.data")
        return []

    data = route["data"]
    raw_persons = data.get("persons") or []
    return raw_persons


def _map_person(raw: Dict) -> Dict:
    first_name = raw.get("firstName") or ""
    last_name = raw.get("lastName") or ""
    parts = [p.strip() for p in [first_name, last_name] if p and p.strip()]
    if len(parts) >= 2 and parts[1].casefold() in parts[0].casefold():
        nombre = parts[0]
    else:
        nombre = " ".join(parts) if parts else "Sin nombre"

    return {
        "nombre": nombre,
        "cedula": raw.get("idNumber") or "",
        "estado": raw.get("status") or "",
        "ubicacion": raw.get("lastSeen") or "",
        "info": raw.get("description") or "",
        "foto_path": raw.get("photoUrl") or "",
        "fuente": "VenezuelaTeBusca",
    }


class VenezuelaTeBuscaAPI:
    def __init__(self, base_url: str = BASE_URL, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def buscar(self, query: str) -> List[Dict]:
        cleaned = " ".join(query.split())
        if not cleaned:
            return []

        try:
            rows = await asyncio.to_thread(self._buscar_sync, cleaned)
            return [_map_person(p) for p in rows]
        except Exception as e:
            logger.error(f"VenezuelaTeBusca search failed: {e}")
            return []

    def _buscar_sync(self, query: str) -> List[Dict]:
        with httpx.Client(timeout=self.timeout, headers=HEADERS) as client:
            resp = client.get(f"{self.base_url}/_root.data", params={"query": query})
            resp.raise_for_status()
            decoded = _decode_flattened_response(resp.json())
        return _extract_persons(decoded)

    def formatear_resultado(self, persona: Dict) -> str:
        nombre = persona.get("nombre", "Sin nombre")
        cedula = persona.get("cedula", "")
        estado = persona.get("estado", "")
        ubicacion = persona.get("ubicacion", "")

        partes = [f"*{nombre}*"]
        if estado:
            partes.append(f"Estado: {estado}")
        if cedula:
            partes.append(f"Cedula: {cedula}")
        if ubicacion:
            partes.append(f"Ubicacion: {ubicacion}")
        partes.append("Fuente: VenezuelaTeBusca")
        return "\n".join(partes)
