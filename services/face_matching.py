import logging
from typing import Optional, List, Tuple

import numpy as np

from config import Config
from services.database import Database

logger = logging.getLogger(__name__)

_facerec = None
_db = None


def get_facerec():
    global _facerec
    if _facerec is None:
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
            import facerec
            _facerec = facerec
            logger.info("facerec module loaded successfully")
        except ImportError as e:
            logger.warning(f"Could not load facerec: {e}")
            _facerec = None
    return _facerec


def get_db():
    global _db
    if _db is None:
        _db = Database()
    return _db


class FaceMatcher:
    def __init__(self):
        self.threshold = Config.FACE_MATCH_THRESHOLD
        self.enabled = Config.FACE_MATCH_ENABLED

    def extract_embedding(self, image_bytes: bytes) -> Optional[np.ndarray]:
        if not self.enabled:
            logger.info("Face matching disabled")
            return None

        facerec = get_facerec()
        if facerec is None:
            logger.warning("facerec not available")
            return None

        try:
            records = facerec.analyze_bytes(image_bytes)
            if not records:
                logger.warning("No face detected in image")
                return None
            return records[0].normed_embedding
        except Exception as e:
            logger.error(f"Error extracting embedding: {e}")
            return None

    def store_embedding(self, persona_id: int, embedding: np.ndarray):
        db = get_db()
        db.guardar_embedding(persona_id, embedding)

    def search(self, probe: np.ndarray) -> List[Tuple[str, float]]:
        db = get_db()
        results = db.buscar_por_facial(probe)
        return [(p.nombre, score) for p, score in results]

    def buscar_personas(self, probe: np.ndarray) -> List[Tuple]:
        db = get_db()
        return db.buscar_por_facial(probe)

    def clear(self):
        pass
