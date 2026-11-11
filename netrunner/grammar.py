"""Gramáticas de NetRunner DSL y cálculo de FIRST, FOLLOW y tabla LL(1).

Una gramática es una lista de producciones ``(izquierda, [derecha])``.
Los no terminales se escriben entre ángulos (``<programa>``); cualquier otro
símbolo es terminal y coincide con ``Token.terminal``. La producción vacía
se escribe ``["ε"]``.

Cada alternativa ocupa una posición en la lista: ese índice (desde 0) es el
que guarda la tabla LL(1). La regla del documento es R(índice + 1): R1 ... R28.
"""

from __future__ import annotations

Production = tuple[str, list[str]]
Grammar = list[Production]
Cell = tuple[str, str]

EPSILON = "ε"
END = "$"

# Las ocho acciones de <accion> (R11-R18), comunes a G1 y G2.
_ACCIONES: list[list[str]] = [
    ["SCAN", "PORTS"],
    ["CONNECT", "PORT", "NUM"],
    ["BYPASS", "FIREWALL"],
    ["DISABLE", "FIREWALL"],
    ["INJECT", "PAYLOAD", "STRING"],
    ["EXECUTE", "SCRIPT", "STRING"],
    ["EXFIL", "DATA"],
    ["CLEAR", "LOGS"],
]

# G1 (sección 2.4 del documento): sin ambigüedad, pero con recursividad por
# la izquierda y prefijos comunes; por eso su tabla predictiva tiene conflictos.
ORIGINAL_GRAMMAR: Grammar = [
    ("<programa>", ["TARGET", "NODE", "HEX_ADDR", "<bloque>"]),
    ("<bloque>", ["{", "<lista>", "}"]),
    ("<lista>", ["<lista>", "<instruccion>"]),
    ("<lista>", ["<instruccion>"]),
    ("<instruccion>", ["<secuencia>", ";"]),
    ("<instruccion>", ["<condicional>"]),
    ("<secuencia>", ["<secuencia>", "->", "<accion>"]),
    ("<secuencia>", ["<accion>"]),
    *[("<accion>", derecha) for derecha in _ACCIONES],
    ("<condicional>", ["IF", "<condicion>", "THEN", "<bloque>"]),
    ("<condicional>", ["IF", "<condicion>", "THEN", "<bloque>", "ELSE", "<bloque>"]),
    ("<condicion>", ["ICE_LEVEL", ">", "NUM"]),
    ("<condicion>", ["ICE_LEVEL", "<", "NUM"]),
    ("<condicion>", ["ICE_LEVEL", "==", "NUM"]),
    ("<condicion>", ["FIREWALL", "==", "ACTIVE"]),
    ("<condicion>", ["FIREWALL", "==", "INACTIVE"]),
]

# G2 (sección 2.8, Tabla 6): gramática final LL(1). La posición i de la
# lista es la regla R(i+1).
LL1_GRAMMAR: Grammar = [
    ("<programa>", ["TARGET", "NODE", "HEX_ADDR", "<bloque>"]),           # R1
    ("<bloque>", ["{", "<lista_instr>", "}"]),                            # R2
    ("<lista_instr>", ["<instruccion>", "<lista_instr'>"]),               # R3
    ("<lista_instr'>", ["<instruccion>", "<lista_instr'>"]),              # R4
    ("<lista_instr'>", [EPSILON]),                                        # R5
    ("<instruccion>", ["<secuencia>", ";"]),                              # R6
    ("<instruccion>", ["<condicional>"]),                                 # R7
    ("<secuencia>", ["<accion>", "<secuencia'>"]),                        # R8
    ("<secuencia'>", ["->", "<accion>", "<secuencia'>"]),                 # R9
    ("<secuencia'>", [EPSILON]),                                          # R10
    *[("<accion>", derecha) for derecha in _ACCIONES],                    # R11-R18
    ("<condicional>", ["IF", "<condicion>", "THEN", "<bloque>", "<resto_if>"]),  # R19
    ("<resto_if>", ["ELSE", "<bloque>"]),                                 # R20
    ("<resto_if>", [EPSILON]),                                            # R21
    ("<condicion>", ["ICE_LEVEL", "<op_rel>", "NUM"]),                    # R22
    ("<condicion>", ["FIREWALL", "==", "<estado>"]),                      # R23
    ("<op_rel>", [">"]),                                                  # R24
    ("<op_rel>", ["<"]),                                                  # R25
    ("<op_rel>", ["=="]),                                                 # R26
    ("<estado>", ["ACTIVE"]),                                             # R27
    ("<estado>", ["INACTIVE"]),                                           # R28
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
    """Nombre de la regla como en el documento: "R1", "R2", ..."""
    return f"R{index + 1}"


def format_production(grammar: Grammar, index: int) -> str:
    """Texto de una regla con su número, p. ej. "R11  <accion> ::= SCAN PORTS"."""
    izquierda, derecha = grammar[index]
    return f"{production_label(grammar, index):<4} {izquierda} ::= {' '.join(derecha)}"


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
    """Gramática en BNF, un no terminal por línea con sus alternativas."""
    lineas: list[str] = []
    for nt in nonterminals(grammar):
        alternativas = [" ".join(d) for izq, d in grammar if izq == nt]
        prefijo = f"{nt} ::= "
        lineas.append(prefijo + alternativas[0])
        for alternativa in alternativas[1:]:
            lineas.append(" " * (len(prefijo) - 2) + "| " + alternativa)
    return "\n".join(lineas)


def format_original_grammar() -> str:
    """Gramática G1 (con recursión por la izquierda y prefijos comunes)."""
    return "Gramática G1\n\n" + format_grammar(ORIGINAL_GRAMMAR)


def format_ll1_grammar() -> str:
    """Gramática final G2 con sus 28 reglas numeradas (R1-R28)."""
    lineas = [format_production(LL1_GRAMMAR, i) for i in range(len(LL1_GRAMMAR))]
    return "Gramática final G2 (LL(1))\n\n" + "\n".join(lineas)


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
