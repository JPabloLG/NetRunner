"""Punto de entrada de NetRunner Analyzer.

Uso:
    python main.py archivo.nr           analiza el archivo en la consola
                                        (imprime el árbol o los errores)
    python main.py                      abre la interfaz gráfica
    python main.py archivo.nr --gui     abre la interfaz gráfica con el archivo

El modo consola no importa Tkinter: la GUI solo se importa al iniciarla.
NetRunner Analyzer analiza el código, nunca lo ejecuta.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from netrunner.diagnostics import LEXICO, Diagnostic
from netrunner.lexer import Lexer
from netrunner.parser import Parser
from netrunner.tokens import Token
from netrunner.tree import simplify, to_ascii, to_dot, to_svg

EXIT_OK = 0
EXIT_ERRORES = 1
EXIT_ARCHIVO = 2

_ETIQUETAS = {LEXICO: "Léxico"}


class _FormatoEspanol(argparse.HelpFormatter):
    """Muestra "uso:" en lugar del encabezado en inglés de argparse."""

    def add_usage(self, usage, actions, groups, prefix=None):  # type: ignore[override]
        super().add_usage(usage, actions, groups, prefix="uso: ")


def construir_argumentos() -> argparse.ArgumentParser:
    """Define los argumentos de la línea de comandos."""
    ap = argparse.ArgumentParser(
        prog="main.py",
        description=("NetRunner Analyzer: analizador léxico y sintáctico de "
                     "NetRunner DSL. Con un archivo lo analiza en la consola; "
                     "sin archivo (o con --gui) abre la interfaz gráfica."),
        formatter_class=_FormatoEspanol,
        add_help=False,
    )
    ap._positionals.title = "argumentos"
    ap._optionals.title = "opciones"
    ap.add_argument("-h", "--help", action="help",
                    help="mostrar esta ayuda y salir")
    ap.add_argument("archivo", nargs="?", help="archivo .nr a analizar")
    ap.add_argument("--cli", action="store_true",
                    help="analizar en la consola (es lo predeterminado con archivo)")
    ap.add_argument("--gui", action="store_true",
                    help="abrir el archivo en la interfaz gráfica")
    ap.add_argument("--tokens", action="store_true",
                    help="mostrar la tabla de tokens reconocidos")
    ap.add_argument("--simplificar", action="store_true",
                    help="mostrar y exportar el árbol simplificado")
    ap.add_argument("--dot", metavar="SALIDA.dot",
                    help="exportar el árbol en formato Graphviz DOT")
    ap.add_argument("--svg", metavar="SALIDA.svg",
                    help="exportar el árbol como imagen SVG")
    return ap


# ---------------------------------------------------------------------------
# Modo consola
# ---------------------------------------------------------------------------


def formatear_diagnostico(d: Diagnostic) -> str:
    """``[Léxico] 4:16  mensaje`` o ``[Sintáctico] 3:5  mensaje``."""
    etiqueta = _ETIQUETAS.get(d.kind, "Sintáctico")
    return f"[{etiqueta}] {d.line}:{d.col}  {d.message}"


def formatear_tokens(tokens: list[Token]) -> str:
    """Tabla legible de tokens: posición, tipo y lexema."""
    filas = [("Pos", "Tipo", "Lexema")]
    filas += [(f"{t.line}:{t.col}", t.type.name, t.lexeme or "(fin)") for t in tokens]
    ancho_pos = max(len(f[0]) for f in filas)
    ancho_tipo = max(len(f[1]) for f in filas)
    lineas = [f"{p:<{ancho_pos}}  {ti:<{ancho_tipo}}  {lx}" for p, ti, lx in filas]
    lineas.insert(1, "-" * (ancho_pos + ancho_tipo + 12))
    return "\n".join(lineas)


def ejecutar_cli(args: argparse.Namespace) -> int:
    """Analiza el archivo e imprime el árbol o los errores."""
    if not args.archivo:
        print("Error: el modo --cli necesita un archivo .nr", file=sys.stderr)
        return EXIT_ARCHIVO
    ruta = Path(args.archivo)
    try:
        fuente = ruta.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: no existe el archivo '{ruta}'", file=sys.stderr)
        return EXIT_ARCHIVO
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error: no se pudo leer '{ruta}': {e}", file=sys.stderr)
        return EXIT_ARCHIVO

    lex = Lexer(fuente).tokenize()
    resultado = Parser(lex.tokens).parse()
    errores = sorted(lex.errors + resultado.errors, key=lambda d: (d.line, d.col))

    arbol = resultado.tree
    if arbol is not None and args.simplificar:
        arbol = simplify(arbol)

    if errores:
        print(f"Se encontraron {len(errores)} error(es):")
        for d in errores:
            print(formatear_diagnostico(d))
    elif arbol is not None:
        print(to_ascii(arbol))

    if args.tokens:
        print()
        print(formatear_tokens(lex.tokens))

    if args.dot or args.svg:
        if arbol is None:
            print("No se exporta el árbol porque hay errores.", file=sys.stderr)
        else:
            if args.dot:
                Path(args.dot).write_text(to_dot(arbol) + "\n", encoding="utf-8")
                print(f"Árbol DOT exportado a {args.dot}")
            if args.svg:
                Path(args.svg).write_text(to_svg(arbol), encoding="utf-8")
                print(f"Árbol SVG exportado a {args.svg}")

    return EXIT_ERRORES if errores else EXIT_OK


# ---------------------------------------------------------------------------
# Modo gráfico
# ---------------------------------------------------------------------------


def ejecutar_gui(archivo: str | None) -> int:
    """Importa la GUI solo ahora y la inicia."""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print(
            "No se encontró Tkinter, necesario para la interfaz gráfica.\n"
            "En Debian/Ubuntu instálalo con:  sudo apt install python3-tk\n"
            "Mientras tanto puedes usar el modo consola:  "
            "python main.py archivo.nr",
            file=sys.stderr,
        )
        return EXIT_ERRORES

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass

    from netrunner.gui.app import run

    run(archivo)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada: decide entre consola y GUI."""
    sys.setrecursionlimit(10000)
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")  # árbol con ├── y ε en Windows
        except (AttributeError, ValueError):
            pass
    args = construir_argumentos().parse_args(argv)
    if args.gui or (not args.archivo and not args.cli):
        return ejecutar_gui(args.archivo)
    return ejecutar_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
