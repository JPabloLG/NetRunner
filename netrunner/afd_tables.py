"""Tablas de transición de los cinco AFD de NetRunner (Fase 1).

Cada familia de tokens tiene su propio AFD; todos comparten el estado
inicial ``q0``. Como los símbolos que salen de ``q0`` son disjuntos entre
familias, la unión de los cinco AFD sigue siendo determinista.

Una tabla es un diccionario ``estado -> {símbolo: destino}``. El símbolo puede
ser un carácter literal (por ejemplo ``">"``) o el nombre de una clase de
símbolos (por ejemplo ``"NZ"``). La función ``classify`` de cada familia
traduce el carácter real leído a los símbolos de la tabla.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from netrunner.tokens import RESERVED_WORDS

# ---------------------------------------------------------------------------
# Clasificación de símbolos (conjuntos ASCII explícitos)
# ---------------------------------------------------------------------------

ZERO: frozenset[str] = frozenset("0")
NZ: frozenset[str] = frozenset("123456789")
X: frozenset[str] = frozenset("x")
HEXL: frozenset[str] = frozenset("abcdefABCDEF")
BLANK: frozenset[str] = frozenset(" \t\r\n")
# NOT_NL y ANY_STR son complementos (infinitos), por eso se definen como
# predicados dentro de los clasificadores y no como conjuntos.

DIGITS: frozenset[str] = ZERO | NZ
UPPER: frozenset[str] = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
LOWER: frozenset[str] = frozenset("abcdefghijklmnopqrstuvwxyz")
# Caracteres que pueden formar un candidato alfanumérico: [A-Za-z0-9_].
CANDIDATE_CHARS: frozenset[str] = UPPER | LOWER | DIGITS | frozenset("_")

# Conjuntos finitos de cada clase, usados para expandir tablas en pruebas
# y en la interfaz.
SYMBOL_CLASSES: dict[str, frozenset[str]] = {
    "ZERO": ZERO,
    "NZ": NZ,
    "X": X,
    "HEXL": HEXL,
    "BLANK": BLANK,
}

Table = dict[str, dict[str, str]]
Accept = dict[str, str]
Classifier = Callable[[str], tuple[str, ...]]


def classify_literal(c: str) -> tuple[str, ...]:
    """El símbolo de la tabla es el propio carácter (trie y operadores)."""
    return (c,)


def classify_num(c: str) -> tuple[str, ...]:
    """Clasifica un carácter para el AFD de enteros y hexadecimales."""
    if c in ZERO:
        return ("ZERO",)
    if c in NZ:
        return ("NZ",)
    if c in X:
        return ("X",)
    if c in HEXL:
        return ("HEXL",)
    return ()


def classify_str(c: str) -> tuple[str, ...]:
    """Clasifica un carácter para el AFD de cadenas de texto."""
    if c == '"':
        return ('"',)
    if c == "\n":
        return ()
    return ("ANY_STR",)


def classify_ws(c: str) -> tuple[str, ...]:
    """Clasifica un carácter para el AFD de comentarios y espacios.

    Un carácter puede pertenecer a varias clases (un espacio es BLANK y
    NOT_NL). Se devuelven en orden; ``run_afd`` usa la primera que tenga
    transición. En ningún estado coinciden dos de ellas, así que no hay
    ambigüedad.
    """
    simbolos: list[str] = []
    if c == "/":
        simbolos.append("/")
    if c in BLANK:
        simbolos.append("BLANK")
    if c != "\n":
        simbolos.append("NOT_NL")
    return tuple(simbolos)


# ---------------------------------------------------------------------------
# Tabla 2: enteros y direcciones hexadecimales
# ---------------------------------------------------------------------------

NUM_AFD: Table = {
    "q0": {"ZERO": "q1", "NZ": "q2"},
    "q1": {"ZERO": "q2", "NZ": "q2", "X": "q3"},
    "q2": {"ZERO": "q2", "NZ": "q2"},
    "q3": {"ZERO": "q4", "NZ": "q4", "HEXL": "q4"},
    "q4": {"ZERO": "q4", "NZ": "q4", "HEXL": "q4"},
}

# q3 (prefijo "0x") no es de aceptación.
NUM_ACCEPT: Accept = {
    "q1": "TK_NUM",
    "q2": "TK_NUM",
    "q4": "HEX_ADDR",
}

# ---------------------------------------------------------------------------
# Tabla 3: cadenas de texto
# ---------------------------------------------------------------------------

STR_AFD: Table = {
    "q0": {'"': "q5"},
    "q5": {'"': "q6", "ANY_STR": "q5"},
}

STR_ACCEPT: Accept = {"q6": "STRING"}

# ---------------------------------------------------------------------------
# Tabla 4: operadores y delimitadores
# ---------------------------------------------------------------------------

OPS_AFD: Table = {
    "q0": {
        ">": "q7",
        "=": "q8",
        "-": "q10",
        "{": "q12",
        "}": "q13",
        ";": "q14",
        "<": "q18",
    },
    "q8": {"=": "q9"},
    "q10": {">": "q11"},
}

OPS_ACCEPT: Accept = {
    "q7": "TK_MAYOR",
    "q9": "TK_IGUAL",
    "q11": "TK_OP",
    "q12": "TK_IZQ",
    "q13": "TK_DER",
    "q14": "TK_DELIM",
    "q18": "TK_MENOR",
}

# ---------------------------------------------------------------------------
# Tabla 5: comentarios y espacios en blanco
# ---------------------------------------------------------------------------

WS_AFD: Table = {
    "q0": {"/": "q15", "BLANK": "q17"},
    "q15": {"/": "q16"},
    "q16": {"NOT_NL": "q16"},
    "q17": {"BLANK": "q17"},
}

WS_ACCEPT: Accept = {
    "q16": "COMENTARIO",
    "q17": "ESPACIO",
}

# ---------------------------------------------------------------------------
# Tabla 1: palabras reservadas (trie)
# ---------------------------------------------------------------------------


def build_keyword_afd(words: tuple[str, ...]) -> tuple[Table, Accept]:
    """Construye el AFD en forma de trie para las palabras dadas.

    Cada estado se llama como el prefijo leído hasta ese momento ("T",
    "TA", "TAR", ...), salvo el inicial, que es ``q0``. Las palabras que
    comparten prefijo comparten estados. Un estado es de aceptación si su
    prefijo es una palabra completa; puede además tener transiciones hacia
    palabras más largas (PORT -> PORTS).
    """
    table: Table = {"q0": {}}
    accept: Accept = {}
    for word in words:
        estado = "q0"
        for i, letra in enumerate(word):
            destino = word[: i + 1]
            table[estado][letra] = destino
            table.setdefault(destino, {})
            estado = destino
        accept[estado] = "TK_CMD"
    return table, accept


KEYWORD_AFD, KEYWORD_ACCEPT = build_keyword_afd(RESERVED_WORDS)

# ---------------------------------------------------------------------------
# Ejecución genérica de un AFD
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunResult:
    """Resultado de recorrer un AFD desde una posición del texto.

    Atributos:
        start: índice donde empezó el recorrido.
        trace: transiciones realizadas (estado, carácter leído, destino).
        accept_state: último estado de aceptación alcanzado, o None.
        accept_pos: índice justo después del último carácter aceptado
            (igual a ``start`` si nunca se aceptó).
        token_name: nombre del token del último estado de aceptación.
        dead_state: estado en el que el autómata se detuvo.
        stop_pos: índice del carácter que no tuvo transición (o fin del texto).
    """

    start: int
    trace: tuple[tuple[str, str, str], ...]
    accept_state: str | None
    accept_pos: int
    token_name: str | None
    dead_state: str
    stop_pos: int

    @property
    def accepted(self) -> bool:
        """True si se alcanzó al menos un estado de aceptación."""
        return self.accept_state is not None

    @property
    def accepted_trace(self) -> tuple[tuple[str, str, str], ...]:
        """Traza recortada hasta el último estado de aceptación (retroceso)."""
        return self.trace[: self.accept_pos - self.start]


def run_afd(
    table: Table,
    accept: Accept,
    text: str,
    start: int,
    classify: Classifier,
) -> RunResult:
    """Recorre el AFD desde ``start`` aplicando máxima coincidencia.

    Avanza mientras exista transición, recordando el último estado de
    aceptación y su posición. Al detenerse, quien llama "retrocede" a esa
    posición: el lexema es ``text[start:accept_pos]``.
    """
    estado = "q0"
    pos = start
    trace: list[tuple[str, str, str]] = []
    accept_state: str | None = None
    accept_pos = start

    while pos < len(text):
        c = text[pos]
        transiciones = table.get(estado, {})
        destino = None
        for simbolo in classify(c):
            if simbolo in transiciones:
                destino = transiciones[simbolo]
                break
        if destino is None:
            break
        trace.append((estado, c, destino))
        estado = destino
        pos += 1
        if estado in accept:
            accept_state = estado
            accept_pos = pos

    return RunResult(
        start=start,
        trace=tuple(trace),
        accept_state=accept_state,
        accept_pos=accept_pos,
        token_name=accept.get(accept_state) if accept_state else None,
        dead_state=estado,
        stop_pos=pos,
    )


# ---------------------------------------------------------------------------
# Familias de AFD
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AFDFamily:
    """Un AFD completo: nombre, tabla, aceptación y clasificador."""

    name: str
    table: Table
    accept: Accept
    classify: Classifier

    def run(self, text: str, start: int) -> RunResult:
        """Ejecuta este AFD sobre ``text`` desde ``start``."""
        return run_afd(self.table, self.accept, text, start, self.classify)


KEYWORD_FAMILY = AFDFamily(
    "AFD palabras reservadas (Tabla 1)",
    KEYWORD_AFD, KEYWORD_ACCEPT, classify_literal,
)
NUM_FAMILY = AFDFamily(
    "AFD enteros y hexadecimales (Tabla 2)", NUM_AFD, NUM_ACCEPT, classify_num
)
STR_FAMILY = AFDFamily(
    "AFD cadenas de texto (Tabla 3)", STR_AFD, STR_ACCEPT, classify_str
)
OPS_FAMILY = AFDFamily(
    "AFD operadores y delimitadores (Tabla 4)",
    OPS_AFD, OPS_ACCEPT, classify_literal,
)
WS_FAMILY = AFDFamily(
    "AFD comentarios y espacios (Tabla 5)", WS_AFD, WS_ACCEPT, classify_ws
)

FAMILIES: tuple[AFDFamily, ...] = (
    KEYWORD_FAMILY, NUM_FAMILY, STR_FAMILY, OPS_FAMILY, WS_FAMILY,
)


def initial_symbols(family: AFDFamily) -> frozenset[str]:
    """Caracteres concretos con transición desde q0 en una familia.

    Las clases de símbolos se expanden a sus caracteres.
    """
    caracteres: set[str] = set()
    for simbolo in family.table["q0"]:
        caracteres |= SYMBOL_CLASSES.get(simbolo, frozenset(simbolo))
    return frozenset(caracteres)
