"""Acceso a los programas de ejemplo de NetRunner DSL."""

from __future__ import annotations

from pathlib import Path

# Carpeta examples/ en la raíz del proyecto, resuelta desde este archivo
# para que funcione sin importar el directorio de trabajo.
EXAMPLES_DIR: Path = Path(__file__).resolve().parent.parent / "examples"

EXAMPLES: list[str] = [
    "ok_1_completo.nr",
    "ok_2_minimo.nr",
    "ok_3_anidado.nr",
    "error_1_mixto.nr",
    "error_2_lexico.nr",
    "error_3_falta_llave.nr",
    "error_4_if_sin_then.nr",
]


def read_example(nombre: str) -> str:
    """Devuelve el contenido del ejemplo indicado.

    Acepta el nombre con o sin la extensión ``.nr``.

    Raises:
        ValueError: si el nombre no corresponde a un ejemplo conocido.
    """
    archivo = nombre if nombre.endswith(".nr") else f"{nombre}.nr"
    if archivo not in EXAMPLES:
        raise ValueError(f"Ejemplo desconocido: {nombre!r}")
    return (EXAMPLES_DIR / archivo).read_text(encoding="utf-8")
