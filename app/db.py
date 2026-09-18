"""Historial de consultas en SQLite.

Vive en data/historial.db, dentro del proyecto, para que sobreviva al reinicio de
la aplicacion sin necesidad de instalar ningun motor de base de datos.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

RUTA_DB = Path(__file__).resolve().parent.parent / "data" / "historial.db"


def _conexion() -> sqlite3.Connection:
    RUTA_DB.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(RUTA_DB)
    conexion.row_factory = sqlite3.Row
    return conexion


def iniciar() -> None:
    with _conexion() as conexion:
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS consultas (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                creada_en TEXT NOT NULL,
                pregunta  TEXT NOT NULL,
                respuesta TEXT NOT NULL
            )
            """
        )


def guardar(pregunta: str, respuesta: dict) -> None:
    with _conexion() as conexion:
        conexion.execute(
            "INSERT INTO consultas (creada_en, pregunta, respuesta) VALUES (?, ?, ?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                pregunta,
                json.dumps(respuesta, ensure_ascii=False),
            ),
        )


def historial(limite: int = 20) -> list[dict]:
    with _conexion() as conexion:
        filas = conexion.execute(
            "SELECT id, creada_en, pregunta, respuesta FROM consultas "
            "ORDER BY id DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [
        {
            "id": f["id"],
            "creada_en": f["creada_en"],
            "pregunta": f["pregunta"],
            "respuesta": json.loads(f["respuesta"]),
        }
        for f in filas
    ]
