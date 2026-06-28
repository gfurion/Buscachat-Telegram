import logging
from typing import List, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://api.acopiove.org/v1"


class AcopioVEAPI:
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=10)

    async def buscar_personas(self, query: str) -> List[Dict]:
        if not query or len(query) < 2:
            return []

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                params = {"q": query}
                async with session.get(f"{BASE_URL}/personas", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("data", [])
                    elif resp.status == 429:
                        logger.warning("Rate limit from AcopioVE /personas")
                        return []
                    else:
                        logger.warning(f"AcopioVE /personas returned status {resp.status}")
                        return []
        except aiohttp.ClientError as e:
            logger.error(f"Connection error calling AcopioVE /personas: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error calling AcopioVE /personas: {e}")
            return []

    async def buscar_puntos(
        self,
        tipo: str = "refugio",
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        radius: int = 10,
        ciudad: Optional[str] = None,
    ) -> List[Dict]:
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                params = {"tipo": tipo}
                if lat is not None and lng is not None:
                    params["near"] = f"{lat},{lng}"
                    params["radius"] = str(radius)
                elif ciudad:
                    params["ciudad"] = ciudad

                async with session.get(f"{BASE_URL}/puntos", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("data", [])
                    elif resp.status == 429:
                        logger.warning("Rate limit from AcopioVE /puntos")
                        return []
                    else:
                        logger.warning(f"AcopioVE /puntos returned status {resp.status}")
                        return []
        except aiohttp.ClientError as e:
            logger.error(f"Connection error calling AcopioVE /puntos: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error calling AcopioVE /puntos: {e}")
            return []

    async def buscar_telefonos(self, ciudad: Optional[str] = None) -> List[Dict]:
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                params = {}
                if ciudad:
                    params["ciudad"] = ciudad

                async with session.get(f"{BASE_URL}/telefonos", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("data", [])
                    elif resp.status == 429:
                        logger.warning("Rate limit from AcopioVE /telefonos")
                        return []
                    else:
                        logger.warning(f"AcopioVE /telefonos returned status {resp.status}")
                        return []
        except aiohttp.ClientError as e:
            logger.error(f"Connection error calling AcopioVE /telefonos: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error calling AcopioVE /telefonos: {e}")
            return []

    def formatear_punto(self, punto: Dict) -> str:
        nombre = punto.get("nombre", punto.get("name", "Sin nombre"))
        ciudad = punto.get("ciudad", "")
        recibe = punto.get("recibe", [])
        distancia = punto.get("distance_km")

        partes = [f"*{nombre}*"]
        if ciudad:
            partes.append(f"   Ciudad: {ciudad}")
        if recibe:
            partes.append(f"   Recibe: {', '.join(recibe)}")
        if distancia is not None:
            partes.append(f"   Distancia: {distancia:.1f} km")

        return "\n".join(partes)

    def formatear_telefono(self, tel: Dict) -> str:
        nombre = tel.get("nombre", tel.get("name", "Sin nombre"))
        telefono = tel.get("telefono", tel.get("phone", ""))
        ciudad = tel.get("ciudad", "")

        partes = [f"*{nombre}*"]
        if telefono:
            partes.append(f"   Tel: {telefono}")
        if ciudad:
            partes.append(f"   Ciudad: {ciudad}")

        return "\n".join(partes)
