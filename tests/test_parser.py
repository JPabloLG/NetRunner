"""Pruebas del analizador sintáctico LL(1)."""

import random

import pytest

from netrunner.diagnostics import Diagnostic
from netrunner.examples import read_example
from netrunner.lexer import Lexer
from netrunner.parser import MAX_ERRORS, Parser, ParseResult, describe_expected
from netrunner.tokens import RESERVED_WORDS
from netrunner.tree import frontier


def analizar(src: str) -> tuple[list[Diagnostic], ParseResult]:
    lx = Lexer(src).tokenize()
    return lx.errors, Parser(lx.tokens).parse()


def sintacticos(src: str) -> list[str]:
    return [e.message for e in analizar(src)[1].errors]


def ok(src: str) -> ParseResult:
    lexicos, r = analizar(src)
    assert lexicos == [] and r.errors == [], [e.message for e in lexicos + r.errors]
    assert r.tree is not None
    return r


# --- Programas válidos ----------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        "TARGET NODE 0x1 { SCAN PORTS; }",
        "TARGET NODE 0x1 { SCAN PORT 22; CONNECT PORT 8080; BYPASS FIREWALL; "
        "DISABLE FIREWALL; INJECT PAYLOAD \"p\"; EXECUTE SCRIPT \"s\"; "
        "EXFIL DATA; CLEAR LOGS; }",
        "TARGET NODE 0x1 { SCAN PORTS -> SCAN PORT 1 -> EXFIL DATA -> CLEAR LOGS; }",
        "TARGET NODE 0x1 { IF FIREWALL == ACTIVE THEN { DISABLE FIREWALL; } }",
        "TARGET NODE 0x1 { IF FIREWALL == INACTIVE THEN { SCAN PORTS; } "
        "ELSE { BYPASS FIREWALL; } }",
        "TARGET NODE 0x1 { IF ICE_LEVEL > 3 THEN { SCAN PORTS; } }",
        "TARGET NODE 0x1 { IF ICE_LEVEL < 3 THEN { SCAN PORTS; } }",
        "TARGET NODE 0x1 { IF ICE_LEVEL == 3 THEN { SCAN PORTS; } }",
        # anidado
        "TARGET NODE 0x1 { IF ICE_LEVEL > 1 THEN { IF FIREWALL == ACTIVE THEN "
        "{ BYPASS FIREWALL; } ELSE { SCAN PORTS; } CLEAR LOGS; } EXFIL DATA; }",
        # comentarios en medio
        "// inicio\nTARGET NODE 0x1 { // abre\n SCAN PORTS; // fin\n}\n",
    ],
)
def test_programas_validos(src: str) -> None:
    r = ok(src)
    assert frontier(r.tree) == [t.lexeme for t in Lexer(src).tokenize().tokens[:-1]]


def test_objetivos_multiples() -> None:
    r = ok("TARGET NODE 0x1 { SCAN PORTS; } TARGET NODE 0x2 { CLEAR LOGS; } "
           "TARGET NODE 0x3 { EXFIL DATA; }")
    objetivos = [n for n in _preorden(r.tree) if n.symbol == "<objetivo>"]
    assert len(objetivos) == 3


def _preorden(raiz):
    pila = [raiz]
    while pila:
        n = pila.pop()
        yield n
        pila.extend(reversed(n.children))


# --- Errores ------------------------------------------------------------------


def test_archivo_vacio() -> None:
    errores, r = analizar("")
    assert r.tree is None
    assert [e.message for e in r.errors] == [
        "Se esperaba 'TARGET', pero se encontró fin de archivo"
    ]


def test_solo_comentarios() -> None:
    assert sintacticos("// nada\n   // más nada\n") == [
        "Se esperaba 'TARGET', pero se encontró fin de archivo"
    ]


def test_bloque_vacio() -> None:
    _, r = analizar("TARGET NODE 0x1 { }")
    assert r.tree is None
    assert [e.message for e in r.errors] == [
        "Se esperaba una instrucción, pero se encontró '}'"
    ]
    assert (r.errors[0].line, r.errors[0].col) == (1, 19)
    assert r.errors[0].kind == "SINTACTICO"


def test_falta_llave_de_cierre() -> None:
    assert sintacticos("TARGET NODE 0x1 {\n SCAN PORTS;\n") == [
        "Se esperaba una instrucción o '}', pero se encontró fin de archivo"
    ]


def test_falta_llave_de_apertura() -> None:
    assert sintacticos("TARGET NODE 0x1 SCAN PORTS; }")[0] == (
        "Se esperaba '{', pero se encontró 'SCAN'"
    )


def test_if_sin_then() -> None:
    mensajes = sintacticos(
        "TARGET NODE 0x1 { IF FIREWALL == ACTIVE { BYPASS FIREWALL; } }"
    )
    assert mensajes[0] == "Se esperaba 'THEN', pero se encontró '{'"


@pytest.mark.parametrize(
    ("src", "mensaje"),
    [
        ("TARGET NODE { SCAN PORTS; }",
         "Se esperaba una dirección hexadecimal, pero se encontró '{'"),
        ("TARGET NODE 0x1 { SCAN PORT; }",
         "Se esperaba un número entero, pero se encontró ';'"),
        ("TARGET NODE 0x1 { INJECT PAYLOAD; }",
         "Se esperaba una cadena entre comillas, pero se encontró ';'"),
        ("TARGET NODE 0x1 { SCAN PORTS }",
         "Se esperaba ';' o '->', pero se encontró '}'"),
        ("TARGET NODE 0x1 { SCAN DATA; }",
         "Se esperaba 'PORT' o 'PORTS', pero se encontró 'DATA'"),
        ("TARGET NODE 0x1 { IF ICE_LEVEL 3 THEN { SCAN PORTS; } }",
         "Se esperaba '==', '>' o '<', pero se encontró '3'"),
        ("TARGET NODE 0x1 { IF FIREWALL == 3 THEN { SCAN PORTS; } }",
         "Se esperaba 'ACTIVE' o 'INACTIVE', pero se encontró '3'"),
        ("TARGET NODE 0x1 { IF DATA THEN { SCAN PORTS; } }",
         "Se esperaba 'FIREWALL' o 'ICE_LEVEL', pero se encontró 'DATA'"),
        ("TARGET NODE 0x1 { IF FIREWALL == ACTIVE THEN { SCAN PORTS; } DATA }",
         "Se esperaba una instrucción, '}' o 'ELSE', pero se encontró 'DATA'"),
    ],
)
def test_mensajes(src: str, mensaje: str) -> None:
    assert sintacticos(src)[0] == mensaje


def test_describe_expected() -> None:
    assert describe_expected({"$"}) == "fin de archivo"
    assert describe_expected({"TARGET", "$"}) == "'TARGET' o fin de archivo"
    assert describe_expected({"HEX_ADDR", "TK_NUM", "STRING"}) == (
        "una dirección hexadecimal, un número entero o una cadena entre comillas"
    )


def test_token_fuera_de_objetivo() -> None:
    _, r = analizar("SCAN PORTS; TARGET NODE 0x1 { SCAN PORTS; }")
    assert [e.message for e in r.errors] == ["Se esperaba 'TARGET', pero se encontró 'SCAN'"]
    _, r = analizar("TARGET NODE 0x1 { SCAN PORTS; } } TARGET NODE 0x2 { CLEAR LOGS; }")
    assert [e.message for e in r.errors] == [
        "Se esperaba 'TARGET' o fin de archivo, pero se encontró '}'"
    ]


def test_recuperacion_nivel_sentencia() -> None:
    _, r = analizar(
        "TARGET NODE 0x1 {\n"
        "  SCAN PORT;\n"           # error 1
        "  CLEAR LOGS;\n"
        "  CONNECT 22;\n"           # error 2
        "  EXFIL DATA;\n"
        "}\n"
        "TARGET NODE 0x2 { BYPASS; }\n"  # error 3
    )
    assert [(e.line, e.message) for e in r.errors] == [
        (2, "Se esperaba un número entero, pero se encontró ';'"),
        (4, "Se esperaba 'PORT', pero se encontró '22'"),
        (7, "Se esperaba 'FIREWALL', pero se encontró ';'"),
    ]
    assert r.tree is None


def test_basura_dentro_del_bloque_se_recupera() -> None:
    _, r = analizar("TARGET NODE 0x1 { SCAN PORTS; PORT 2; CLEAR LOGS; }")
    assert [e.message for e in r.errors] == [
        "Se esperaba una instrucción o '}', pero se encontró 'PORT'"
    ]


def test_sin_errores_duplicados_en_la_misma_posicion() -> None:
    _, r = analizar("TARGET NODE 0x1 { SCAN PORTS; ")
    posiciones = [(e.line, e.col) for e in r.errors]
    assert len(posiciones) == len(set(posiciones))


def test_after_lex_error_en_mensaje() -> None:
    lexicos, r = analizar("TARGET NODE 0x1 { SCAN PORTS @ }")
    assert len(lexicos) == 1
    assert r.errors[0].message == (
        "Se esperaba ';' o '->', pero se encontró '}' "
        "(posible consecuencia de un error léxico anterior)"
    )


def test_maximo_100_errores() -> None:
    _, r = analizar("TARGET NODE 0x1 {" + " SCAN DATA;" * 300 + " }")
    assert len(r.errors) == MAX_ERRORS


def test_mecanismo_expected() -> None:
    lx = Lexer("TARGET NODE").tokenize()
    p = Parser(lx.tokens)
    assert not p.check("NODE")
    assert p.check("TARGET")
    assert p.expected == {"NODE"}
    p.advance()
    assert p.expected == set()


def test_parser_acepta_tokens_con_auxiliares() -> None:
    lx = Lexer("TARGET NODE 0x1 { // c\n SCAN PORTS; }").tokenize()
    assert Parser(lx.all_tokens).parse().errors == []


# --- Robustez -----------------------------------------------------------------


def test_2000_sentencias_sin_recursion() -> None:
    r = ok("TARGET NODE 0x1 {\n" + "    SCAN PORTS -> CLEAR LOGS;\n" * 2000 + "}\n")
    assert r.tree.count() > 2000


def test_2000_objetivos() -> None:
    ok("TARGET NODE 0x1 { SCAN PORTS; }\n" * 2000)


VOCABULARIO = list(RESERVED_WORDS) + [
    "{", "}", ";", "->", ">", "<", "==", "=", "-", "/", "//x\n", "0x1F", "0x",
    "22", "007", '"s"', '"abierta', "@", ".", "scan", "\n", "\t",
]


def test_200_cadenas_aleatorias() -> None:
    rng = random.Random(2026)
    for _ in range(200):
        src = " ".join(rng.choice(VOCABULARIO) for _ in range(rng.randint(0, 60)))
        lexicos, r = analizar(src)
        assert len(r.errors) <= MAX_ERRORS
        assert (r.tree is None) == bool(r.errors)
        if r.tree is not None:
            assert frontier(r.tree) == [
                t.lexeme for t in Lexer(src).tokenize().tokens[:-1]
            ]


def test_200_cadenas_aleatorias_de_caracteres() -> None:
    rng = random.Random(7)
    alfabeto = "TARGETNODEIFSCAN0123456789xabcdef{};->=</\"\n \t@.ñ_"
    for _ in range(200):
        src = "".join(rng.choice(alfabeto) for _ in range(rng.randint(0, 120)))
        _, r = analizar(src)
        assert len(r.errors) <= MAX_ERRORS


# --- Archivos de ejemplo ----------------------------------------------------------
# Se omiten mientras los archivos .nr estén vacíos (falta su contenido oficial).


def _ejemplo(nombre: str) -> str:
    texto = read_example(nombre)
    if not texto.strip():
        pytest.skip(f"{nombre} está vacío: falta el contenido oficial del ejemplo")
    return texto


@pytest.mark.parametrize("nombre", ["ok_1_completo", "ok_2_minimo", "ok_3_anidado"])
def test_ejemplos_validos(nombre: str) -> None:
    src = _ejemplo(nombre)
    r = ok(src)
    assert frontier(r.tree) == [t.lexeme for t in Lexer(src).tokenize().tokens[:-1]]


def test_error_1_mixto_tres_diagnosticos() -> None:
    lexicos, r = analizar(_ejemplo("error_1_mixto"))
    assert len(lexicos) + len(r.errors) == 3
    assert r.tree is None


def test_error_2_lexico() -> None:
    lexicos, _ = analizar(_ejemplo("error_2_lexico"))
    assert lexicos


def test_error_3_falta_llave() -> None:
    _, r = analizar(_ejemplo("error_3_falta_llave"))
    assert r.tree is None
    # El ejemplo omite la llave de apertura tras la dirección hexadecimal.
    assert any("'{'" in e.message for e in r.errors)


def test_error_4_if_sin_then() -> None:
    _, r = analizar(_ejemplo("error_4_if_sin_then"))
    assert r.tree is None
    assert any("'THEN'" in e.message for e in r.errors)


# --- Equivalencia con un analizador LL(1) de pila dirigido por la tabla -------------


def _parser_por_tabla(tokens):
    """Analizador predictivo no recursivo (pila + tabla de grammar.py).

    Sirve de referencia: el descenso recursivo debe aceptar exactamente lo
    mismo y construir exactamente el mismo árbol.
    """
    from netrunner.grammar import LL1_GRAMMAR, build_ll1_table
    from netrunner.tree import Node

    tabla = build_ll1_table(LL1_GRAMMAR)
    no_terminales = {a for a, _ in LL1_GRAMMAR}
    raiz = Node("<programa>")
    pila = [("$", None), ("<programa>", raiz)]
    i = 0
    while pila:
        simbolo, nodo = pila.pop()
        token = tokens[i]
        if simbolo == "$":
            return raiz if token.terminal == "$" else None
        if simbolo not in no_terminales:
            if token.terminal != simbolo:
                return None
            nodo.symbol, nodo.token = token.type.name, token
            i += 1
            continue
        indice = tabla.get((simbolo, token.terminal))
        if indice is None:
            return None
        derecha = LL1_GRAMMAR[indice][1]
        nodo.children = [Node(s) for s in derecha]
        for s, hijo in reversed(list(zip(derecha, nodo.children))):
            if s != "ε":
                pila.append((s, hijo))
    return None


def _generar(rng, simbolo="<programa>", prof=0):
    """Programa aleatorio derivado de LL1_GRAMMAR (lista de terminales)."""
    from netrunner.grammar import LL1_GRAMMAR

    alternativas = [d for a, d in LL1_GRAMMAR if a == simbolo]
    if not alternativas:
        return [simbolo]
    if prof > 7:
        # Alternativas que terminan pronto (sin abrir objetivos/bloques nuevos).
        cortas = {"<programa'>": ["ε"], "<lista_sent'>": ["ε"], "<secuencia'>": ["ε"],
                  "<condicional'>": ["ε"], "<sentencia>": ["<secuencia>", ";"],
                  "<accion>": ["EXFIL", "DATA"]}
        alternativas = [cortas.get(simbolo, alternativas[0])]
    salida = []
    for s in rng.choice(alternativas):
        if s != "ε":
            salida += _generar(rng, s, prof + 1)
    return salida


def _firma(raiz):
    from netrunner.tree import preorder

    return [(n.symbol, len(n.children), n.token.lexeme if n.token else None, d)
            for n, d in preorder(raiz)]


LEXEMAS = {"TK_NUM": "22", "HEX_ADDR": "0x1F", "STRING": '"s"'}


def test_descenso_recursivo_equivale_al_parser_por_tabla() -> None:
    rng = random.Random(42)
    for _ in range(300):
        src = " ".join(LEXEMAS.get(t, t) for t in _generar(rng))
        lexicos, r = analizar(src)
        assert lexicos == [] and r.errors == [], src
        referencia = _parser_por_tabla(Lexer(src).tokenize().tokens)
        assert referencia is not None
        assert _firma(r.tree) == _firma(referencia)


def test_aceptacion_igual_al_parser_por_tabla_en_mutaciones() -> None:
    rng = random.Random(7)
    vocab = ["TARGET", "NODE", "0x1", "{", "}", ";", "->", "SCAN", "PORT", "PORTS",
             "22", '"s"', "IF", "THEN", "ELSE", "ICE_LEVEL", "FIREWALL", "==", ">"]
    for _ in range(500):
        terminos = [LEXEMAS.get(t, t) for t in _generar(rng)]
        k = rng.randrange(len(terminos))
        if rng.random() < 0.5:
            del terminos[k]
        else:
            terminos[k] = rng.choice(vocab)
        src = " ".join(terminos)
        lx = Lexer(src).tokenize()
        aceptado = Parser(lx.tokens).parse().tree is not None
        assert aceptado == (_parser_por_tabla(lx.tokens) is not None), src
