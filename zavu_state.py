import logging
from typing import Optional

import numpy as np

from models.persona import Persona, TipoReporte
from services.database import Database
from services.face_matching import FaceMatcher

logger = logging.getLogger(__name__)

db = Database()
face_matcher = FaceMatcher()

NOMBRE = "reportar:step:nombre"
CEDULA = "reportar:step:cedula"
UBICACION = "reportar:step:ubicacion"
FOTO = "reportar:step:foto"
CONFIRMAR = "reportar:step:confirmar"


class ReportStateMachine:
    _states: dict[str, dict] = {}

    @classmethod
    def is_active(cls, chat_id: str) -> bool:
        return chat_id in cls._states

    @classmethod
    def get_route(cls, chat_id: str) -> Optional[str]:
        state = cls._states.get(chat_id)
        if not state:
            return None
        step = state["step"]
        if step == FOTO:
            return "reportar:step:foto"
        return "reportar:step:text"

    @classmethod
    def start(cls, chat_id: str, tipo: str) -> str:
        cls._states[chat_id] = {
            "step": NOMBRE,
            "tipo": tipo,
            "nombre": None,
            "cedula": None,
            "ubicacion": None,
            "foto_path": None,
            "foto_file_id": None,
        }
        tipo_text = "desaparecido/a" if tipo == "desaparecido" else "encontrado/a"
        return f"*Reportar persona {tipo_text}*\n\nCual es el nombre completo de la persona?"

    @classmethod
    def handle_text(cls, chat_id: str, text: str) -> Optional[str]:
        state = cls._states.get(chat_id)
        if not state:
            return None

        step = state["step"]
        text = text.strip()

        # Universal escapes — work at ANY step
        if text in ("/cancel", "Cancelar", "/start"):
            cls.cancel(chat_id)
            return None

        if step == NOMBRE:
            return cls._step_nombre(state, text)
        elif step == CEDULA:
            return cls._step_cedula(state, text)
        elif step == UBICACION:
            return cls._step_ubicacion(state, text)
        elif step == FOTO:
            return cls._step_foto_skip(state, text)
        elif step == CONFIRMAR:
            return cls._step_confirmar(chat_id, state, text)

        return None

    @classmethod
    def handle_photo(cls, chat_id: str, media_url: str) -> Optional[str]:
        state = cls._states.get(chat_id)
        if not state or state["step"] != FOTO:
            return None
        state["foto_path"] = media_url
        state["step"] = CONFIRMAR
        return cls._build_summary(state)

    @classmethod
    def set_embedding(cls, chat_id: str, embedding: np.ndarray) -> None:
        state = cls._states.get(chat_id)
        if state:
            state["embedding"] = embedding

    @classmethod
    def _step_nombre(cls, state: dict, text: str) -> Optional[str]:
        if len(text) < 2:
            return "El nombre debe tener al menos 2 caracteres. Proba de nuevo:"
        state["nombre"] = text
        state["step"] = CEDULA
        return f"Nombre: *{text}*\n\nCual es el numero de cedula?\nEscribi /skip si no sabes."

    @classmethod
    def _step_cedula(cls, state: dict, text: str) -> Optional[str]:
        if text == "/skip":
            state["cedula"] = ""
        elif not text.isdigit():
            return "La cedula debe contener solo numeros. Proba de nuevo o escribi /skip:"
        else:
            state["cedula"] = text
        state["step"] = UBICACION
        return "En que ubicacion fue vista por ultima vez?\nEscribi /skip si no sabes."

    @classmethod
    def _step_ubicacion(cls, state: dict, text: str) -> Optional[str]:
        if text == "/skip":
            state["ubicacion"] = ""
        else:
            state["ubicacion"] = text
        state["step"] = FOTO
        return "Envia una foto de la persona.\nEscribi /skip si no tenes."

    @classmethod
    def _step_foto_skip(cls, state: dict, text: str) -> Optional[str]:
        if text == "/skip":
            state["foto_path"] = None
            state["foto_file_id"] = None
            state["step"] = CONFIRMAR
            return cls._build_summary(state)
        return "Envia una foto o escribi /skip si no tenes."

    @classmethod
    def _step_confirmar(cls, chat_id: str, state: dict, text: str) -> Optional[str]:
        if text.lower() != "confirmar":
            return "Escribi *Confirmar* para guardar o *Cancelar* para descartar."

        return cls._save_report(chat_id, state)

    @classmethod
    def _save_report(cls, chat_id: str, state: dict) -> Optional[str]:
        tipo = TipoReporte.DESAPARECIDO if state["tipo"] == "desaparecido" else TipoReporte.ENCONTRADO
        persona = Persona(
            nombre=state.get("nombre", ""),
            cedula=state.get("cedula", ""),
            ubicacion=state.get("ubicacion", ""),
            foto_path=state.get("foto_path"),
            foto_file_id=state.get("foto_file_id"),
            tipo=tipo,
            reporter_chat_id=int(chat_id) if chat_id.isdigit() else 0,
        )

        try:
            persona_id = db.guardar_persona(persona)
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            cls.cancel(chat_id)
            return "Error al guardar el reporte. Proba de nuevo con /start."

        embedding = state.get("embedding")
        if embedding is not None:
            try:
                face_matcher.store_embedding(persona_id, embedding)
                logger.info(f"Embedding saved for persona_id={persona_id}")
            except Exception as e:
                logger.error(f"Error saving embedding: {e}")

        tipo_text = "desaparecido/a" if persona.tipo == TipoReporte.DESAPARECIDO else "encontrado/a"
        cls.cancel(chat_id)
        return (
            f"*Reporte guardado correctamente*\n\n"
            f"ID: #{persona_id}\n"
            f"Nombre: {persona.nombre}\n"
            f"Tipo: {tipo_text}\n\n"
            "Escribi /start para volver al menu."
        )

    @classmethod
    def _build_summary(cls, state: dict) -> str:
        tipo = state["tipo"]
        tipo_text = "desaparecido/a" if tipo == "desaparecido" else "encontrado/a"
        return (
            f"*Resumen del reporte*\n\n"
            f"Tipo: *{tipo_text}*\n"
            f"Nombre: *{state.get('nombre', '-')}*\n"
            f"Cedula: {state.get('cedula') or 'No informada'}\n"
            f"Ubicacion: {state.get('ubicacion') or 'No informada'}\n"
            f"Foto: {'Enviada' if state.get('foto_path') else 'No enviada'}\n\n"
            "Escribi *Confirmar* para guardar o *Cancelar* para descartar."
        )

    @classmethod
    def cancel(cls, chat_id: str):
        cls._states.pop(chat_id, None)
        logger.info(f"Report state cancelled for chat_id={chat_id}")
