from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional


class TipoReporte(str, Enum):
    DESAPARECIDO = "desaparecido"
    ENCONTRADO = "encontrado"


@dataclass
class Persona:
    id: Optional[int] = None
    nombre: str = ""
    cedula: str = ""
    ubicacion: str = ""
    descripcion: str = ""
    foto_path: Optional[str] = None
    foto_file_id: Optional[str] = None
    tipo: TipoReporte = TipoReporte.DESAPARECIDO
    reporter_chat_id: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
