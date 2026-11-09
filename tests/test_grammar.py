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
)

ACCIONES = {"SCAN", "CONNECT", "BYPASS", "DISABLE", "INJECT", "EXECUTE", "EXFIL", "CLEAR"}
SENTENCIAS = ACCIONES | {"IF"}

FIRST_ESPERADO = {
    "<programa>": {"TARGET"},
    "<objetivo>": {"TARGET"},
    "<programa'>": {"TARGET", EPSILON},
    "<bloque>": {"{"},
    "<lista_sent>": SENTENCIAS,
    "<sentencia>": SENTENCIAS,
    "<lista_sent'>": SENTENCIAS | {EPSILON},
    "<secuencia>": ACCIONES,
    "<accion>": ACCIONES,
    "<secuencia'>": {"->", EPSILON},
    "<accion'>": {"PORTS", "PORT"},
    "<condicional>": {"IF"},
    "<condicional'>": {"ELSE", EPSILON},
    "<condicion>": {"ICE_LEVEL", "FIREWALL"},
    "<comp>": {">", "<", "=="},
    "<estado>": {"ACTIVE", "INACTIVE"},
}

FOLLOW_ESPERADO = {
    "<programa>": {"$"},
    "<programa'>": {"$"},
    "<objetivo>": {"TARGET", "$"},
    "<bloque>": {"TARGET", "$", "ELSE", "}"} | SENTENCIAS,
    "<lista_sent>": {"}"},
    "<lista_sent'>": {"}"},
    "<sentencia>": SENTENCIAS | {"}"},
    "<condicional>": SENTENCIAS | {"}"},
    "<condicional'>": SENTENCIAS | {"}"},
    "<secuencia>": {";"},
    "<secuencia'>": {";"},
    "<accion>": {"->", ";"},
    "<accion'>": {"->", ";"},
    "<condicion>": {"THEN"},
    "<estado>": {"THEN"},
    "<comp>": {"TK_NUM"},
}


def test_first_exactos() -> None:
    assert compute_first(LL1_GRAMMAR) == FIRST_ESPERADO


def test_follow_exactos() -> None:
    assert compute_follow(LL1_GRAMMAR, "<programa>") == FOLLOW_ESPERADO


def test_tabla_ll1_sin_conflictos() -> None:
    tabla = build_ll1_table(LL1_GRAMMAR)
    assert find_conflicts(tabla) == {}
    assert tabla[("<accion>", "SCAN")] == 13
    assert tabla[("<secuencia'>", ";")] == 12  # producción ε vía FOLLOW
    assert tabla[("<programa'>", "$")] == 2
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
    assert ("<programa>", "TARGET") in conflictos
    assert ("<accion>", "SCAN") in conflictos
    assert ("<condicional>", "IF") in conflictos


def test_cantidad_de_producciones_y_reglas() -> None:
    assert len(nonterminals(LL1_GRAMMAR)) == 16
    assert len(LL1_GRAMMAR) == 33
    assert len(nonterminals(ORIGINAL_GRAMMAR)) == 11
    assert len(ORIGINAL_GRAMMAR) == 28


@pytest.mark.parametrize(
    ("indice", "etiqueta"),
    [(0, "1"), (1, "2a"), (2, "2b"), (3, "3"), (13, "10a"), (20, "10h"),
     (21, "11a"), (32, "16b")],
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
    assert "<programa> ::= <programa> <objetivo>" in format_original_grammar()
    texto = format_ll1_grammar()
    assert "16. <estado> ::= ACTIVE" in texto
    assert "| ε" in texto
    assert "FOLLOW = { ; }" in format_first_follow()
    tabla = format_ll1_table()
    assert "10a. <accion> ::= SCAN <accion'>" in tabla
    assert tabla.endswith("Conflictos: 0")
