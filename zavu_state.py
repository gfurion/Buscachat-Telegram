import json
import logging
from typing import Optional

from models.persona import Persona, TipoReporte
from services.database import get_db
from services.normalizer import escape_md

logger = logging.getLogger(__name__)

db = get_db()

NOMBRE = "reportar:step:nombre"
CEDULA = "reportar:step:cedula"
UBICACION = "reportar:step:ubicacion"
FOTO = "reportar:step:foto"
CONFIRMAR = "reportar:step:confirmar"


class ReportStateMachine:
    _states: dict[str, dict] = {}

    @classmethod
    def _persist(cls, chat_id: str) -> None:
        state = cls._states.get(chat_id)
        if state:
            db.save_conversation_state(chat_id, json.dumps(state))
        else:
            db.delete_conversation_state(chat_id)

    @classmethod
    def _load(cls, chat_id: str) -> Optional[dict]:
        if chat_id in cls._states:
            return cls._states[chat_id]
        data = db.load_conversation_state(chat_id)
        if data:
            cls._states[chat_id] = json.loads(data)
            return cls._states[chat_id]
        return None

    @classmethod
    def is_active(cls, chat_id: str) -> bool:
        return cls._load(chat_id) is not None

    @classmethod
    def get_route(cls, chat_id: str) -> Optional[str]:
        state = cls._load(chat_id)
        if not state:
            return None
        if state["step"] == FOTO:
            return "photo:report"
        return "reportar:step:text"

    @classmethod
    def start(cls, chat_id: str, tipo: str) -> str:
        logger.info(f"Reportar start: tipo={tipo} chat_id={chat_id}")
        cls._states[chat_id] = {
            "step": NOMBRE,
            "tipo": tipo,
            "nombre": None,
            "cedula": None,
            "ubicacion": None,
            "foto_path": None,
            "foto_file_id": None,
        }
        cls._persist(chat_id)
        tipo_text = "desaparecido/a" if tipo == "desaparecido" else "encontrado/a"
        return f"*Reportar persona {tipo_text}*\n\nCual es el nombre completo de la persona?"

    @classmethod
    def handle_text(cls, chat_id: str, text: str) -> Optional[str]:
        state = cls._load(chat_id)
        if not state:
            return None

        step = state["step"]
        text = text.strip()

        # Universal escapes — work at ANY step
        if text in ("/cancel", "Cancelar", "/start"):
            cls.cancel(chat_id)
            return None

        if step == NOMBRE:
            result = cls._step_nombre(state, text)
        elif step == CEDULA:
            result = cls._step_cedula(state, text)
        elif step == UBICACION:
            result = cls._step_ubicacion(state, text)
        elif step == FOTO:
            result = cls._step_foto(state, text)
        elif step == CONFIRMAR:
            result = cls._step_confirmar(chat_id, state, text)
        else:
            result = None

        if result is not None and chat_id in cls._states:
            cls._persist(chat_id)

        return result

    @classmethod
    def _step_nombre(cls, state: dict, text: str) -> Optional[str]:
        if len(text) < 2:
            return "El nombre debe tener al menos 2 caracteres. Proba de nuevo:"
        if len(text) > 200:
            return "El nombre es demasiado largo (maximo 200 caracteres). Proba de nuevo:"
        state["nombre"] = text
        state["step"] = CEDULA
        return f"Nombre: *{escape_md(text)}*\n\nCual es el numero de cedula?\nEscribi /skip si no sabes."

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
        elif len(text) > 300:
            return "La ubicacion es demasiado larga (maximo 300 caracteres). Proba de nuevo:"
        else:
            state["ubicacion"] = text
        state["step"] = FOTO
        return "📸 *Foto de la persona*\n\nAdjuntá una foto de la persona que estás reportando.\nO escribí /skip si no tenés foto."

    @classmethod
    def _step_foto(cls, state: dict, text: str) -> Optional[str]:
        if text == "/skip":
            state["step"] = CONFIRMAR
            return cls._build_summary(state)
        return "📸 Adjuntá una foto de la persona o escribí /skip para omitir."

    @classmethod
    def save_photo(cls, chat_id: str, foto_path: str, foto_file_id: str) -> str:
        state = cls._load(chat_id)
        if not state:
            return ""
        state["foto_path"] = foto_path
        state["foto_file_id"] = foto_file_id
        state["step"] = CONFIRMAR
        cls._persist(chat_id)
        return cls._build_summary(state)

    @classmethod
    def _step_confirmar(cls, chat_id: str, state: dict, text: str) -> Optional[str]:
        if text.lower() != "confirmar":
            return "Escribi *Confirmar* para guardar o *Cancelar* para descartar."

        return cls._save_report(chat_id, state)

    @classmethod
    def _save_report(cls, chat_id: str, state: dict) -> Optional[str]:
        tipo_str = state.get("tipo", "desaparecido")
        tipo = TipoReporte.DESAPARECIDO if tipo_str == "desaparecido" else TipoReporte.ENCONTRADO
        logger.info(f"Save report: tipo_str={tipo_str} tipo={tipo.value} chat_id={chat_id}")
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

        tipo_text = "desaparecido/a" if persona.tipo == TipoReporte.DESAPARECIDO else "encontrado/a"
        cls.cancel(chat_id)
        return (
            f"*Reporte guardado correctamente*\n\n"
            f"ID: #{persona_id}\n"
            f"Nombre: {escape_md(persona.nombre)}\n"
            f"Tipo: {tipo_text}\n\n"
            "Escribi /start para volver al menu."
        )

    @classmethod
    def _build_summary(cls, state: dict) -> str:
        tipo_str = state.get("tipo", "desaparecido")
        tipo_text = "desaparecido/a" if tipo_str == "desaparecido" else "encontrado/a"
        foto_status = "✅ Adjuntada" if state.get("foto_file_id") else "❌ No adjuntada"
        logger.info(f"Build summary: tipo_str={tipo_str} tipo_text={tipo_text}")
        nombre = escape_md(state.get("nombre", "-") or "-")
        ubicacion = escape_md(state.get("ubicacion") or "No informada")
        cedula = state.get("cedula") or "No informada"
        return (
            f"*Resumen del reporte*\n\n"
            f"Tipo: *{tipo_text}*\n"
            f"Nombre: *{nombre}*\n"
            f"Cedula: {cedula}\n"
            f"Ubicacion: {ubicacion}\n"
            f"Foto: {foto_status}\n\n"
            "Escribi *Confirmar* para guardar o *Cancelar* para descartar."
        )

    @classmethod
    def cancel(cls, chat_id: str):
        cls._states.pop(chat_id, None)
        db.delete_conversation_state(chat_id)
        logger.info(f"Report state cancelled for chat_id={chat_id}")
