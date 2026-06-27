import sqlite3
import logging
import struct
from datetime import datetime, UTC
from typing import List, Optional, Tuple

import numpy as np

from config import Config
from models.persona import Persona, TipoReporte
from services.normalizer import normalizar_texto

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        Config.ensure_dirs()
        self.db_path = str(Config.DB_PATH)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS personas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    cedula TEXT DEFAULT '',
                    ubicacion TEXT DEFAULT '',
                    descripcion TEXT DEFAULT '',
                    foto_path TEXT,
                    foto_file_id TEXT,
                    tipo TEXT NOT NULL DEFAULT 'desaparecido',
                    reporter_chat_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reportes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    persona_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    texto TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (persona_id) REFERENCES personas(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    persona_id INTEGER NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (persona_id) REFERENCES personas(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_personas_nombre ON personas(nombre)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_personas_cedula ON personas(cedula)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_personas_tipo ON personas(tipo)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_persona ON embeddings(persona_id)")
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def guardar_persona(self, persona: Persona) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """INSERT INTO personas
                       (nombre, cedula, ubicacion, descripcion, foto_path,
                        foto_file_id, tipo, reporter_chat_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        persona.nombre,
                        persona.cedula,
                        persona.ubicacion,
                        persona.descripcion,
                        persona.foto_path,
                        persona.foto_file_id,
                        persona.tipo.value,
                        persona.reporter_chat_id,
                        persona.created_at.isoformat(),
                    ),
                )
                conn.commit()
                logger.info(f"Persona saved: id={cursor.lastrowid}, nombre={persona.nombre}")
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Database error saving persona: {e}")
            raise

    def guardar_embedding(self, persona_id: int, embedding: np.ndarray) -> int:
        try:
            embedding_bytes = embedding.astype(np.float32).tobytes()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "INSERT INTO embeddings (persona_id, embedding, created_at) VALUES (?, ?, ?)",
                    (persona_id, embedding_bytes, datetime.now(UTC).isoformat()),
                )
                conn.commit()
                logger.info(f"Embedding saved for persona_id={persona_id}")
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Database error saving embedding: {e}")
            raise

    def buscar_por_facial(self, probe: np.ndarray, top_k: int = 5) -> List[Tuple[Persona, float]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT e.id, e.persona_id, e.embedding,
                              p.nombre, p.cedula, p.ubicacion, p.descripcion,
                              p.foto_path, p.foto_file_id, p.tipo,
                              p.reporter_chat_id, p.created_at
                       FROM embeddings e
                       JOIN personas p ON e.persona_id = p.id"""
                ).fetchall()

                if not rows:
                    return []

                results = []
                for row in rows:
                    stored = np.frombuffer(row["embedding"], dtype=np.float32)
                    similarity = float(np.dot(probe, stored))
                    if similarity >= Config.FACE_MATCH_THRESHOLD:
                        persona = Persona(
                            id=row["persona_id"],
                            nombre=row["nombre"],
                            cedula=row["cedula"],
                            ubicacion=row["ubicacion"],
                            descripcion=row["descripcion"],
                            foto_path=row["foto_path"],
                            foto_file_id=row["foto_file_id"],
                            tipo=TipoReporte(row["tipo"]),
                            reporter_chat_id=row["reporter_chat_id"],
                            created_at=datetime.fromisoformat(row["created_at"]),
                        )
                        results.append((persona, similarity))

                results.sort(key=lambda x: x[1], reverse=True)
                return results[:top_k]
        except sqlite3.Error as e:
            logger.error(f"Database error in facial search: {e}")
            return []

    def buscar_por_nombre(self, nombre: str, tipo: Optional[TipoReporte] = None) -> List[Persona]:
        nombre_norm = normalizar_texto(nombre)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                if tipo:
                    rows = conn.execute(
                        "SELECT * FROM personas WHERE nombre LIKE ? AND tipo = ? ORDER BY created_at DESC LIMIT 10",
                        (f"%{nombre_norm}%", tipo.value),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM personas WHERE nombre LIKE ? ORDER BY created_at DESC LIMIT 10",
                        (f"%{nombre_norm}%",),
                    ).fetchall()
                return [self._row_to_persona(r) for r in rows]
        except sqlite3.Error as e:
            logger.error(f"Database error searching by name: {e}")
            return []

    def buscar_por_cedula(self, cedula: str) -> List[Persona]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM personas WHERE cedula LIKE ? ORDER BY created_at DESC LIMIT 10",
                    (f"%{cedula}%",),
                ).fetchall()
                return [self._row_to_persona(r) for r in rows]
        except sqlite3.Error as e:
            logger.error(f"Database error searching by cedula: {e}")
            return []

    def buscar_por_texto(self, texto: str) -> List[Persona]:
        texto_norm = normalizar_texto(texto)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT * FROM personas
                       WHERE nombre LIKE ? OR cedula LIKE ? OR ubicacion LIKE ?
                       ORDER BY created_at DESC LIMIT 10""",
                    (f"%{texto_norm}%", f"%{texto_norm}%", f"%{texto_norm}%"),
                ).fetchall()
                return [self._row_to_persona(r) for r in rows]
        except sqlite3.Error as e:
            logger.error(f"Database error searching by text: {e}")
            return []

    def contar_por_tipo(self) -> dict:
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT tipo, COUNT(*) as total FROM personas GROUP BY tipo"
                ).fetchall()
                return {row[0]: row[1] for row in rows}
        except sqlite3.Error as e:
            logger.error(f"Database error counting: {e}")
            return {}

    def _row_to_persona(self, row) -> Persona:
        return Persona(
            id=row["id"],
            nombre=row["nombre"],
            cedula=row["cedula"],
            ubicacion=row["ubicacion"],
            descripcion=row["descripcion"],
            foto_path=row["foto_path"],
            foto_file_id=row["foto_file_id"],
            tipo=TipoReporte(row["tipo"]),
            reporter_chat_id=row["reporter_chat_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
