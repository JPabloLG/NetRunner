"""Modelo de diagnósticos (errores) del analizador."""

from __future__ import annotations

from dataclasses import dataclass

LEXICO = "LEXICO"
SINTACTICO = "SINTACTICO"


@dataclass(frozen=True)
class Diagnostic:
    """Error detectado durante el análisis.

    Atributos:
        kind: tipo de error, LEXICO o SINTACTICO.
        line: línea del error (desde 1).
        col: columna del error (desde 1).
        length: cantidad de caracteres a resaltar en el editor.
        message: descripción del error en español.
    """

    kind: str
    line: int
    col: int
    length: int
    message: str
