import logging
from typing import List, Dict, Optional

import aiohttp

from services.normalizer import normalizar_texto

logger = logging.getLogger(__name__)

BASE_URL = "https://reportavnzla.com/api/v1"


class ReportaVNZLAAPI:
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=10)

    async def buscar_personas(
        self,
        query: str = "",
        cedula: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        if not query and not cedula:
            return []

        params: dict = {"limit": str(limit)}
        if query:
            params["q"] = normalizar_texto(query)
        if cedula:
            params["cedula"] = cedula
        if estado:
            params["estado"] = estado

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{BASE_URL}/personas", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("data", [])
                    elif resp.status == 429:
                        logger.warning("Rate limit from ReportaVNZLA /personas")
                        return []
                    else:
                        logger.warning(f"ReportaVNZLA /personas returned status {resp.status}")
                        return []
        except aiohttp.ClientError as e:
            logger.error(f"Connection error calling ReportaVNZLA /personas: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error calling ReportaVNZLA /personas: {e}")
            return []

    def formatear_persona(self, persona: Dict) -> str:
        nombre = persona.get("nombre", "")
        apellido = persona.get("apellido", "")
        nombre_completo = f"{nombre} {apellido}".strip() or "Sin nombre"
        cedula = persona.get("cedula", "")
        estado = persona.get("estado", "?")
        edad = persona.get("edad")
        genero = persona.get("genero", "")
        ubicacion = persona.get("ultimaUbicacion", "")
        descripcion = persona.get("descripcion", "")
        foto = persona.get("fotoUrl", "")

        emoji = {"buscado": "🔍", "encontrado": "📍", "fallecido": "💀"}.get(estado, "❓")
        estado_text = {"buscado": "buscado", "encontrado": "encontrado/a", "fallecido": "fallecido/a"}.get(estado, estado)

        partes = [f"{emoji} *{nombre_completo}* — {estado_text}"]
        if cedula:
            partes.append(f"   CI: {cedula}")
        if edad:
            partes.append(f"   Edad: {edad}")
        if ubicacion:
            partes.append(f"   Ubicacion: {ubicacion}")
        if descripcion:
            partes.append(f"   Notas: {descripcion[:100]}")

        return "\n".join(partes)
