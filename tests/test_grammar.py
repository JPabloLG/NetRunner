"""Pruebas de FIRST, FOLLOW y tabla LL(1)."""

import pytest

from netrunner.grammar import (
    EPSILON,
    LL1_GRAMMAR,
    ORIGINAL_GRAMMAR,
    build_ll1_table,
    compute_first,
    compute_follow,
    find_conflicts,
    first_of_sequence,
    format_first_follow,
    format_ll1_grammar,
    format_ll1_table,
    format_original_grammar,
    nonterminals,
    production_label,
    terminals,
)

# ACC del documento (Tabla 7).
ACC = {"SCAN", "CONNECT", "BYPASS", "DISABLE", "INJECT", "EXECUTE", "EXFIL", "CLEAR"}
INSTRUCCIONES = ACC | {"IF"}

# Tabla 7 del documento: PRIMERO de G2.
FIRST_ESPERADO = {
    "<programa>": {"TARGET"},
    "<bloque>": {"{"},
    "<lista_instr>": INSTRUCCIONES,
    "<lista_instr'>": INSTRUCCIONES | {EPSILON},
    "<instruccion>": INSTRUCCIONES,
    "<secuencia>": ACC,
    "<secuencia'>": {"->", EPSILON},
    "<accion>": ACC,
    "<condicional>": {"IF"},
    "<resto_if>": {"ELSE", EPSILON},
    "<condicion>": {"ICE_LEVEL", "FIREWALL"},
    "<op_rel>": {">", "<", "=="},
    "<estado>": {"ACTIVE", "INACTIVE"},
}

# Tabla 7 del documento: SIGUIENTE de G2.
FOLLOW_ESPERADO = {
    "<programa>": {"$"},
    "<bloque>": INSTRUCCIONES | {"ELSE", "}", "$"},
    "<lista_instr>": {"}"},
    "<lista_instr'>": {"}"},
    "<instruccion>": INSTRUCCIONES | {"}"},
    "<secuencia>": {";"},
    "<secuencia'>": {";"},
    "<accion>": {";", "->"},
    "<condicional>": INSTRUCCIONES | {"}"},
    "<resto_if>": INSTRUCCIONES | {"}"},
    "<condicion>": {"THEN"},
    "<op_rel>": {"NUM"},
    "<estado>": {"THEN"},
}


def test_first_exactos() -> None:
    assert compute_first(LL1_GRAMMAR) == FIRST_ESPERADO


def test_follow_exactos() -> None:
    assert compute_follow(LL1_GRAMMAR, "<programa>") == FOLLOW_ESPERADO


def test_tabla_ll1_sin_conflictos() -> None:
    tabla = build_ll1_table(LL1_GRAMMAR)
    assert find_conflicts(tabla) == {}
    # Tabla 9 del documento (índice = número de regla - 1).
    assert tabla[("<programa>", "TARGET")] == 0      # R1
    assert tabla[("<accion>", "SCAN")] == 10         # R11
    assert tabla[("<secuencia'>", ";")] == 9         # R10 (ε vía SIGUIENTE)
    assert tabla[("<lista_instr'>", "}")] == 4       # R5
    assert tabla[("<resto_if>", "ELSE")] == 19       # R20
    assert tabla[("<resto_if>", "}")] == 20          # R21
    assert tabla[("<estado>", "INACTIVE")] == 27     # R28
    assert ("<accion>", "IF") not in tabla


def test_conflicto_en_gramatica_de_juguete() -> None:
    juguete = [
        ("<A>", ["a", "<B>"]),
        ("<A>", ["a", "<C>"]),
        ("<B>", ["b"]),
        ("<C>", ["c"]),
    ]
    assert find_conflicts(build_ll1_table(juguete)) == {("<A>", "a"): [0, 1]}


def test_gramatica_original_no_es_ll1() -> None:
    conflictos = find_conflicts(build_ll1_table(ORIGINAL_GRAMMAR))
    # G1: recursividad izquierda y prefijos comunes (secciones 2.4-2.6).
    assert ("<lista>", "SCAN") in conflictos
    assert ("<secuencia>", "CLEAR") in conflictos
    assert ("<condicional>", "IF") in conflictos
    assert ("<condicion>", "ICE_LEVEL") in conflictos
    assert ("<condicion>", "FIREWALL") in conflictos


def test_cantidad_de_producciones_y_reglas() -> None:
    # G2 = (ZT, ZN, S, P): 13 no terminales, 33 terminales y 28 reglas.
    assert len(nonterminals(LL1_GRAMMAR)) == 13
    assert len(terminals(LL1_GRAMMAR)) == 33
    assert len(LL1_GRAMMAR) == 28
    assert len(nonterminals(ORIGINAL_GRAMMAR)) == 8
    assert len(ORIGINAL_GRAMMAR) == 23


@pytest.mark.parametrize(
    ("indice", "etiqueta"),
    [(0, "R1"), (4, "R5"), (10, "R11"), (17, "R18"), (18, "R19"), (27, "R28")],
)
def test_indices_de_produccion(indice: int, etiqueta: str) -> None:
    assert production_label(LL1_GRAMMAR, indice) == etiqueta


def test_tratamiento_de_epsilon() -> None:
    first = {"<X>": {"x", EPSILON}, "<Y>": {"y"}}
    assert first_of_sequence([EPSILON], first) == {EPSILON}
    assert first_of_sequence([], first) == {EPSILON}
    assert first_of_sequence(["<X>"], first) == {"x", EPSILON}
    assert first_of_sequence(["<X>", "<Y>"], first) == {"x", "y"}
    assert first_of_sequence(["<X>", "<X>"], first) == {"x", EPSILON}
    assert first_of_sequence(["t", "<X>"], first) == {"t"}


def test_anulables_en_cadena() -> None:
    g = [
        ("<S>", ["<A>", "<B>", "c"]),
        ("<A>", ["a"]),
        ("<A>", [EPSILON]),
        ("<B>", ["b"]),
        ("<B>", [EPSILON]),
    ]
    first = compute_first(g)
    assert first["<S>"] == {"a", "b", "c"}
    follow = compute_follow(g, "<S>")
    assert follow["<A>"] == {"b", "c"}
    assert follow["<B>"] == {"c"}


def test_formateo() -> None:
    assert "<lista> ::= <lista> <instruccion>" in format_original_grammar()
    texto = format_ll1_grammar()
    assert "R1   <programa> ::= TARGET NODE HEX_ADDR <bloque>" in texto
    assert "R21  <resto_if> ::= ε" in texto
    assert "R28  <estado> ::= INACTIVE" in texto
    assert "FOLLOW = { ; }" in format_first_follow()
    tabla = format_ll1_table()
    assert "R11  <accion> ::= SCAN PORTS" in tabla
    assert tabla.endswith("Conflictos: 0")
