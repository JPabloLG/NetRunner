"""Pruebas de las tablas de los cinco AFD y de run_afd."""

from itertools import combinations

import pytest

from netrunner.afd_tables import (
    FAMILIES,
    KEYWORD_ACCEPT,
    KEYWORD_AFD,
    KEYWORD_FAMILY,
    NUM_ACCEPT,
    NUM_FAMILY,
    OPS_FAMILY,
    STR_FAMILY,
    WS_FAMILY,
    build_keyword_afd,
    initial_symbols,
)
from netrunner.tokens import RESERVED_WORDS


# --- Trie de palabras reservadas -------------------------------------------

def test_trie_tiene_111_estados_sin_q0() -> None:
    assert len(KEYWORD_AFD) - 1 == 111


def test_trie_acepta_las_23_palabras() -> None:
    assert len(KEYWORD_ACCEPT) == 23
    for palabra in RESERVED_WORDS:
        assert KEYWORD_ACCEPT[palabra] == "TK_CMD"
        r = KEYWORD_FAMILY.run(palabra, 0)
        assert r.accept_state == palabra
        assert r.accept_pos == len(palabra)


def test_trie_estados_nombrados_por_prefijo() -> None:
    assert KEYWORD_AFD["q0"]["T"] == "T"
    assert KEYWORD_AFD["T"]["A"] == "TA"
    assert KEYWORD_AFD["TARGE"]["T"] == "TARGET"
    assert KEYWORD_AFD["ICE"]["_"] == "ICE_"


def test_port_es_aceptacion_y_continua_a_ports() -> None:
    assert "PORT" in KEYWORD_ACCEPT
    assert KEYWORD_AFD["PORT"] == {"S": "PORTS"}
    assert KEYWORD_FAMILY.run("PORTS", 0).accept_state == "PORTS"


def test_build_keyword_afd_generico() -> None:
    tabla, acepta = build_keyword_afd(("AB", "AC"))
    assert set(tabla) == {"q0", "A", "AB", "AC"}
    assert acepta == {"AB": "TK_CMD", "AC": "TK_CMD"}


def test_prefijo_incompleto_no_acepta() -> None:
    r = KEYWORD_FAMILY.run("SCA", 0)
    assert not r.accepted
    assert r.dead_state == "SCA"


# --- Determinismo -----------------------------------------------------------

def test_simbolos_iniciales_disjuntos_dos_a_dos() -> None:
    for a, b in combinations(FAMILIES, 2):
        assert initial_symbols(a).isdisjoint(initial_symbols(b)), (a.name, b.name)


def test_nombres_de_familias() -> None:
    assert [f.name for f in FAMILIES] == [
        "AFD palabras reservadas (Tabla 1)",
        "AFD enteros y hexadecimales (Tabla 2)",
        "AFD cadenas de texto (Tabla 3)",
        "AFD operadores y delimitadores (Tabla 4)",
        "AFD comentarios y espacios (Tabla 5)",
    ]


# --- Enteros y hexadecimales ------------------------------------------------

@pytest.mark.parametrize(
    ("texto", "estado", "token"),
    [
        ("0", "q1", "TK_NUM"),
        ("7", "q2", "TK_NUM"),
        ("8080", "q2", "TK_NUM"),
        ("007", "q2", "TK_NUM"),
        ("0xad23d", "q4", "HEX_ADDR"),
        ("0xFF", "q4", "HEX_ADDR"),
    ],
)
def test_num_acepta(texto: str, estado: str, token: str) -> None:
    r = NUM_FAMILY.run(texto, 0)
    assert (r.accept_state, r.token_name, r.accept_pos) == (estado, token, len(texto))


def test_q3_no_es_aceptacion() -> None:
    assert "q3" not in NUM_ACCEPT
    r = NUM_FAMILY.run("0x", 0)
    assert r.dead_state == "q3"
    assert r.accept_state == "q1"  # retrocede al "0"
    assert r.accept_pos == 1


def test_maxima_coincidencia_con_retroceso() -> None:
    r = NUM_FAMILY.run("0xg", 0)
    assert r.stop_pos == 2
    assert r.accept_pos == 1
    assert r.accepted_trace == (("q0", "0", "q1"),)


def test_traza_conserva_simbolo_real() -> None:
    r = NUM_FAMILY.run("0xA", 0)
    assert r.trace == (("q0", "0", "q1"), ("q1", "x", "q3"), ("q3", "A", "q4"))


# --- Cadenas ----------------------------------------------------------------

def test_cadena_vacia_y_normal() -> None:
    assert STR_FAMILY.run('""', 0).accept_state == "q6"
    r = STR_FAMILY.run('"hola mundo" x', 0)
    assert r.accept_pos == 12


def test_cadena_no_cruza_salto_de_linea() -> None:
    r = STR_FAMILY.run('"abc\n"', 0)
    assert not r.accepted
    assert r.dead_state == "q5"
    assert r.stop_pos == 4


# --- Operadores -------------------------------------------------------------

@pytest.mark.parametrize(
    ("texto", "token"),
    [("->", "TK_OP"), ("==", "TK_IGUAL"), (">", "TK_MAYOR"), ("<", "TK_MENOR"),
     ("{", "TK_IZQ"), ("}", "TK_DER"), (";", "TK_DELIM")],
)
def test_operadores(texto: str, token: str) -> None:
    r = OPS_FAMILY.run(texto, 0)
    assert r.token_name == token and r.accept_pos == len(texto)


@pytest.mark.parametrize(("texto", "muerto"), [("-", "q10"), ("=", "q8"), ("-x", "q10")])
def test_operadores_incompletos(texto: str, muerto: str) -> None:
    r = OPS_FAMILY.run(texto, 0)
    assert not r.accepted and r.dead_state == muerto


# --- Comentarios y espacios -------------------------------------------------

def test_comentario_hasta_fin_de_linea() -> None:
    r = WS_FAMILY.run("// hola -> {}\nSCAN", 0)
    assert r.token_name == "COMENTARIO"
    assert r.accept_pos == 13


def test_espacios_agrupados() -> None:
    r = WS_FAMILY.run(" \t\r\n  X", 0)
    assert r.token_name == "ESPACIO" and r.accept_pos == 6


def test_barra_sola_no_acepta() -> None:
    r = WS_FAMILY.run("/x", 0)
    assert not r.accepted and r.dead_state == "q15"
