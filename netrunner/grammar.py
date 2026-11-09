"""Gramáticas de NetRunner DSL y cálculo de FIRST, FOLLOW y tabla LL(1).

Una gramática es una lista de producciones ``(izquierda, [derecha])``.
Los no terminales se escriben entre ángulos (``<programa>``); cualquier otro
símbolo es terminal y coincide con ``Token.terminal``. La producción vacía
se escribe ``["ε"]``.

Cada alternativa ocupa una posición en la lista: ese índice (desde 0) es el
que guarda la tabla LL(1). El número de regla que se muestra en la interfaz
(1, 2, ..., 10a, 10b, ...) se deriva del orden de los no terminales.
"""

from __future__ import annotations

Production = tuple[str, list[str]]
Grammar = list[Production]
Cell = tuple[str, str]

EPSILON = "ε"
END = "$"

_ACCIONES_ORIGINAL: list[list[str]] = [
    ["SCAN", "PORTS"],
    ["SCAN", "PORT", "TK_NUM"],
    ["CONNECT", "PORT", "TK_NUM"],
    ["BYPASS", "FIREWALL"],
    ["DISABLE", "FIREWALL"],
    ["INJECT", "PAYLOAD", "STRING"],
    ["EXECUTE", "SCRIPT", "STRING"],
    ["EXFIL", "DATA"],
    ["CLEAR", "LOGS"],
]

ORIGINAL_GRAMMAR: Grammar = [
    ("<programa>", ["<programa>", "<objetivo>"]),
    ("<programa>", ["<objetivo>"]),
    ("<objetivo>", ["TARGET", "NODE", "HEX_ADDR", "<bloque>"]),
    ("<bloque>", ["{", "<lista_sent>", "}"]),
    ("<lista_sent>", ["<lista_sent>", "<sentencia>"]),
    ("<lista_sent>", ["<sentencia>"]),
    ("<sentencia>", ["<secuencia>", ";"]),
    ("<sentencia>", ["<condicional>"]),
    ("<secuencia>", ["<secuencia>", "->", "<accion>"]),
    ("<secuencia>", ["<accion>"]),
    *[("<accion>", derecha) for derecha in _ACCIONES_ORIGINAL],
    ("<condicional>", ["IF", "<condicion>", "THEN", "<bloque>"]),
    ("<condicional>", ["IF", "<condicion>", "THEN", "<bloque>", "ELSE", "<bloque>"]),
    ("<condicion>", ["ICE_LEVEL", "<comp>", "TK_NUM"]),
    ("<condicion>", ["FIREWALL", "==", "<estado>"]),
    ("<comp>", [">"]),
    ("<comp>", ["<"]),
    ("<comp>", ["=="]),
    ("<estado>", ["ACTIVE"]),
    ("<estado>", ["INACTIVE"]),
]

LL1_GRAMMAR: Grammar = [
    # 1
    ("<programa>", ["<objetivo>", "<programa'>"]),
    # 2
    ("<programa'>", ["<objetivo>", "<programa'>"]),
    ("<programa'>", [EPSILON]),
    # 3
    ("<objetivo>", ["TARGET", "NODE", "HEX_ADDR", "<bloque>"]),
    # 4
    ("<bloque>", ["{", "<lista_sent>", "}"]),
    # 5
    ("<lista_sent>", ["<sentencia>", "<lista_sent'>"]),
    # 6
    ("<lista_sent'>", ["<sentencia>", "<lista_sent'>"]),
    ("<lista_sent'>", [EPSILON]),
    # 7
    ("<sentencia>", ["<secuencia>", ";"]),
    ("<sentencia>", ["<condicional>"]),
    # 8
    ("<secuencia>", ["<accion>", "<secuencia'>"]),
    # 9
    ("<secuencia'>", ["->", "<accion>", "<secuencia'>"]),
    ("<secuencia'>", [EPSILON]),
    # 10
    ("<accion>", ["SCAN", "<accion'>"]),
    ("<accion>", ["CONNECT", "PORT", "TK_NUM"]),
    ("<accion>", ["BYPASS", "FIREWALL"]),
    ("<accion>", ["DISABLE", "FIREWALL"]),
    ("<accion>", ["INJECT", "PAYLOAD", "STRING"]),
    ("<accion>", ["EXECUTE", "SCRIPT", "STRING"]),
    ("<accion>", ["EXFIL", "DATA"]),
    ("<accion>", ["CLEAR", "LOGS"]),
    # 11
    ("<accion'>", ["PORTS"]),
    ("<accion'>", ["PORT", "TK_NUM"]),
    # 12
    ("<condicional>", ["IF", "<condicion>", "THEN", "<bloque>", "<condicional'>"]),
    # 13
    ("<condicional'>", ["ELSE", "<bloque>"]),
    ("<condicional'>", [EPSILON]),
    # 14
    ("<condicion>", ["ICE_LEVEL", "<comp>", "TK_NUM"]),
    ("<condicion>", ["FIREWALL", "==", "<estado>"]),
    # 15
    ("<comp>", [">"]),
    ("<comp>", ["<"]),
    ("<comp>", ["=="]),
    # 16
    ("<estado>", ["ACTIVE"]),
    ("<estado>", ["INACTIVE"]),
]

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def nonterminals(grammar: Grammar) -> list[str]:
    """No terminales en el orden en que aparecen por primera vez."""
    vistos: list[str] = []
    for izquierda, _ in grammar:
        if izquierda not in vistos:
            vistos.append(izquierda)
    return vistos


def terminals(grammar: Grammar) -> list[str]:
    """Terminales en el orden en que aparecen (sin ε)."""
    nts = set(nonterminals(grammar))
    vistos: list[str] = []
    for _, derecha in grammar:
        for simbolo in derecha:
            if simbolo not in nts and simbolo != EPSILON and simbolo not in vistos:
                vistos.append(simbolo)
    return vistos


def production_label(grammar: Grammar, index: int) -> str:
    """Número de regla de una alternativa: "3", o "10a", "10b"... si hay varias."""
    izquierda = grammar[index][0]
    numero = nonterminals(grammar).index(izquierda) + 1
    alternativas = [i for i, (izq, _) in enumerate(grammar) if izq == izquierda]
    if len(alternativas) == 1:
        return str(numero)
    return f"{numero}{chr(ord('a') + alternativas.index(index))}"


def format_production(grammar: Grammar, index: int) -> str:
    """Texto de una alternativa con su número, p. ej. "10a. <accion> ::= SCAN <accion'>"."""
    izquierda, derecha = grammar[index]
    return f"{production_label(grammar, index)}. {izquierda} ::= {' '.join(derecha)}"


# ---------------------------------------------------------------------------
# FIRST
# ---------------------------------------------------------------------------


def first_of_sequence(
    sequence: list[str], first: dict[str, set[str]]
) -> set[str]:
    """FIRST de una secuencia de símbolos.

    Se agregan los FIRST de cada símbolo (sin ε) mientras el símbolo sea
    anulable. Si todos lo son (o la secuencia es vacía o ``[ε]``), se
    agrega ε.
    """
    resultado: set[str] = set()
    for simbolo in sequence:
        if simbolo == EPSILON:
            continue
        if simbolo not in first:  # terminal
            resultado.add(simbolo)
            return resultado
        resultado |= first[simbolo] - {EPSILON}
        if EPSILON not in first[simbolo]:
            return resultado
    resultado.add(EPSILON)
    return resultado


def compute_first(grammar: Grammar) -> dict[str, set[str]]:
    """FIRST de cada no terminal mediante punto fijo.

    Se parte de conjuntos vacíos y se recorren todas las producciones
    agregando FIRST(derecha) a FIRST(izquierda) hasta que ningún conjunto
    cambie.
    """
    first: dict[str, set[str]] = {nt: set() for nt in nonterminals(grammar)}
    cambio = True
    while cambio:
        cambio = False
        for izquierda, derecha in grammar:
            nuevos = first_of_sequence(derecha, first) - first[izquierda]
            if nuevos:
                first[izquierda] |= nuevos
                cambio = True
    return first


# ---------------------------------------------------------------------------
# FOLLOW
# ---------------------------------------------------------------------------


def compute_follow(
    grammar: Grammar,
    start: str,
    first: dict[str, set[str]] | None = None,
) -> dict[str, set[str]]:
    """FOLLOW de cada no terminal mediante punto fijo.

    Reglas, para cada producción A ::= α B β:
      1. FOLLOW(inicial) contiene $.
      2. FIRST(β) sin ε se agrega a FOLLOW(B).
      3. Si β es anulable (o vacía), FOLLOW(A) se agrega a FOLLOW(B).
    """
    if first is None:
        first = compute_first(grammar)
    follow: dict[str, set[str]] = {nt: set() for nt in first}
    follow[start].add(END)
    cambio = True
    while cambio:
        cambio = False
        for izquierda, derecha in grammar:
            for i, simbolo in enumerate(derecha):
                if simbolo not in follow:  # terminal o ε
                    continue
                first_beta = first_of_sequence(derecha[i + 1:], first)
                nuevos = first_beta - {EPSILON}
                if EPSILON in first_beta:
                    nuevos |= follow[izquierda]
                nuevos -= follow[simbolo]
                if nuevos:
                    follow[simbolo] |= nuevos
                    cambio = True
    return follow


# ---------------------------------------------------------------------------
# Tabla LL(1)
# ---------------------------------------------------------------------------


class LL1Table(dict[Cell, int]):
    """Tabla predictiva: (no_terminal, terminal) -> índice de producción.

    Cada celda guarda la primera producción asignada. ``candidates`` guarda
    todas las que intentaron ocupar cada celda, para detectar conflictos.
    """

    def __init__(self) -> None:
        super().__init__()
        self.candidates: dict[Cell, list[int]] = {}

    def add(self, cell: Cell, index: int) -> None:
        """Registra la producción ``index`` en la celda ``cell``."""
        lista = self.candidates.setdefault(cell, [])
        if index not in lista:
            lista.append(index)
        self.setdefault(cell, index)


def build_ll1_table(grammar: Grammar) -> LL1Table:
    """Construye la tabla LL(1) de la gramática.

    Para cada producción A ::= α (índice i):
      - para cada terminal a en FIRST(α) sin ε: M[A, a] = i;
      - si ε está en FIRST(α): M[A, b] = i para cada b en FOLLOW(A).
    El símbolo inicial es el lado izquierdo de la primera producción.
    """
    first = compute_first(grammar)
    follow = compute_follow(grammar, grammar[0][0], first)
    tabla = LL1Table()
    for indice, (izquierda, derecha) in enumerate(grammar):
        first_alfa = first_of_sequence(derecha, first)
        for terminal in first_alfa - {EPSILON}:
            tabla.add((izquierda, terminal), indice)
        if EPSILON in first_alfa:
            for terminal in follow[izquierda]:
                tabla.add((izquierda, terminal), indice)
    return tabla


def find_conflicts(table: LL1Table) -> dict[Cell, list[int]]:
    """Celdas a las que intentaron entrar dos o más producciones distintas."""
    return {
        celda: indices
        for celda, indices in table.candidates.items()
        if len(indices) > 1
    }


# ---------------------------------------------------------------------------
# Formateo para la interfaz
# ---------------------------------------------------------------------------


def format_grammar(grammar: Grammar) -> str:
    """Gramática en BNF, una regla numerada por no terminal."""
    lineas: list[str] = []
    for numero, nt in enumerate(nonterminals(grammar), start=1):
        alternativas = [" ".join(d) for izq, d in grammar if izq == nt]
        prefijo = f"{numero:>2}. {nt} ::= "
        lineas.append(prefijo + alternativas[0])
        for alternativa in alternativas[1:]:
            lineas.append(" " * (len(prefijo) - 2) + "| " + alternativa)
    return "\n".join(lineas)


def format_original_grammar() -> str:
    """Gramática original (con recursión por la izquierda)."""
    return "Gramática original\n\n" + format_grammar(ORIGINAL_GRAMMAR)


def format_ll1_grammar() -> str:
    """Gramática LL(1) con sus 16 reglas numeradas."""
    return "Gramática LL(1)\n\n" + format_grammar(LL1_GRAMMAR)


def _formatear_conjunto(simbolos: set[str], orden: list[str]) -> str:
    ordenados = [s for s in orden if s in simbolos]
    return "{ " + ", ".join(ordenados) + " }"


def format_first_follow(grammar: Grammar = LL1_GRAMMAR) -> str:
    """Tabla de texto con FIRST y FOLLOW de cada no terminal."""
    first = compute_first(grammar)
    follow = compute_follow(grammar, grammar[0][0], first)
    orden = terminals(grammar) + [EPSILON, END]
    nts = nonterminals(grammar)
    ancho = max(len(nt) for nt in nts)
    lineas = [f"{'No terminal':<{ancho}}  FIRST / FOLLOW", "-" * (ancho + 40)]
    for nt in nts:
        lineas.append(f"{nt:<{ancho}}  FIRST  = {_formatear_conjunto(first[nt], orden)}")
        lineas.append(f"{'':<{ancho}}  FOLLOW = {_formatear_conjunto(follow[nt], orden)}")
    return "\n".join(lineas)


def format_ll1_table(grammar: Grammar = LL1_GRAMMAR) -> str:
    """Tabla LL(1) agrupada por no terminal: terminal → número de regla."""
    tabla = build_ll1_table(grammar)
    orden = terminals(grammar) + [END]
    lineas: list[str] = []
    for nt in nonterminals(grammar):
        lineas.append(f"M[{nt}, ·]")
        for terminal in orden:
            if (nt, terminal) in tabla:
                indices = tabla.candidates[(nt, terminal)]
                reglas = " / ".join(format_production(grammar, i) for i in indices)
                marca = "  ⚠ CONFLICTO" if len(indices) > 1 else ""
                lineas.append(f"    {terminal:<10} → {reglas}{marca}")
        lineas.append("")
    conflictos = find_conflicts(tabla)
    lineas.append(f"Conflictos: {len(conflictos)}")
    return "\n".join(lineas)
