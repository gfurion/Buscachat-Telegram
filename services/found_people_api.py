import logging
from typing import List, Dict

import aiohttp

from config import Config
from services.normalizer import normalizar_texto

logger = logging.getLogger(__name__)


class FoundPeopleAPI:
    def __init__(self):
        self.base_url = Config.FOUND_PEOPLE_API_URL
        self.timeout = aiohttp.ClientTimeout(total=10)

    async def buscar(self, query: str) -> List[Dict]:
        if not query or len(query) < 2:
            return []

        query_norm = normalizar_texto(query)

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                params = {"q": query_norm, "page": 1, "pageSize": 10}
                async with session.get(
                    f"{self.base_url}/api/v1/found-people",
                    params=params,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("data", [])
                    elif resp.status == 429:
                        logger.warning("Rate limit from found-people API")
                        return []
                    else:
                        logger.warning(f"API returned status {resp.status}")
                        return []
        except aiohttp.ClientError as e:
            logger.error(f"Connection error calling found-people API: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error calling found-people API: {e}")
            return []

    def formatear_resultado(self, persona: Dict) -> str:
        nombre = persona.get("fullName", "Sin nombre")
        info = persona.get("relevantInfo", "")
        cedula = persona.get("documentId", "")
        fuente = persona.get("sourceUrl", "")

        partes = [f"**{nombre}**"]
        if cedula:
            partes.append(f"Cedula: {cedula}")
        if info:
            partes.append(f"Info: {info[:200]}")
        if fuente:
            partes.append(f"Fuente: {fuente}")

        return "\n".join(partes)
