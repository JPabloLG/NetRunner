"""Pruebas del analizador léxico y de sus modelos (tokens, ejemplos)."""

import pytest

from netrunner.diagnostics import Diagnostic
from netrunner.examples import EXAMPLES, read_example
from netrunner.lexer import Lexer, LexResult
from netrunner.tokens import RESERVED_WORDS, Token, TokenType


def _token(tipo: TokenType, lexema: str) -> Token:
    return Token(tipo, lexema, 1, 1, (), "prueba")


def test_palabras_reservadas() -> None:
    assert len(RESERVED_WORDS) == 23
    assert len(set(RESERVED_WORDS)) == 23


def test_tipos_de_token() -> None:
    assert len(TokenType) == 14


@pytest.mark.parametrize(
    ("tipo", "lexema", "terminal"),
    [
        (TokenType.TK_CMD, "SCAN", "SCAN"),
        (TokenType.TK_IZQ, "{", "{"),
        (TokenType.TK_DER, "}", "}"),
        (TokenType.TK_DELIM, ";", ";"),
        (TokenType.TK_OP, "->", "->"),
        (TokenType.TK_MAYOR, ">", ">"),
        (TokenType.TK_MENOR, "<", "<"),
        (TokenType.TK_IGUAL, "==", "=="),
        (TokenType.HEX_ADDR, "0xFF", "HEX_ADDR"),
        (TokenType.TK_NUM, "8080", "TK_NUM"),
        (TokenType.STRING, '"x"', "STRING"),
        (TokenType.EOF, "", "$"),
    ],
)
def test_terminal(tipo: TokenType, lexema: str, terminal: str) -> None:
    assert _token(tipo, lexema).terminal == terminal


def test_token_inmutable_y_longitud() -> None:
    token = _token(TokenType.TK_NUM, "8080")
    assert token.length == 4
    assert token.after_lex_error is False
    with pytest.raises(AttributeError):
        token.lexeme = "1"  # type: ignore[misc]


def test_diagnostic() -> None:
    d = Diagnostic("LEXICO", 2, 5, 1, "Símbolo no válido")
    assert d.kind == "LEXICO"


def test_ejemplos() -> None:
    assert len(EXAMPLES) == 7
    for nombre in EXAMPLES:
        assert isinstance(read_example(nombre), str)
    with pytest.raises(ValueError):
        read_example("no_existe")


# ---------------------------------------------------------------------------
# Analizador léxico
# ---------------------------------------------------------------------------


def lex(texto: str) -> LexResult:
    return Lexer(texto).tokenize()


def tipos(texto: str) -> list[TokenType]:
    return [t.type for t in lex(texto).tokens]


def mensajes(texto: str) -> list[str]:
    return [e.message for e in lex(texto).errors]


NO_RECONOCIDA = ("Palabra no reconocida '{}': NetRunner solo admite sus 23 "
                 "palabras reservadas (no hay identificadores)")


@pytest.mark.parametrize("palabra", RESERVED_WORDS)
def test_cada_palabra_reservada(palabra: str) -> None:
    r = lex(palabra)
    assert not r.errors
    assert r.tokens[0].type is TokenType.TK_CMD
    assert r.tokens[0].lexeme == palabra


def test_port_y_ports() -> None:
    r = lex("PORT PORTS")
    assert [t.lexeme for t in r.tokens[:-1]] == ["PORT", "PORTS"]
    assert not r.errors


def test_programa_valido() -> None:
    codigo = 'TARGET NODE 0xad23d {\n    SCAN PORTS 8080 -> "x";\n}\n'
    r = lex(codigo)
    assert not r.errors
    assert [t.terminal for t in r.tokens] == [
        "TARGET", "NODE", "HEX_ADDR", "{", "SCAN", "PORTS", "TK_NUM", "->",
        "STRING", ";", "}", "$",
    ]


def test_tokens_vs_all_tokens() -> None:
    r = lex("SCAN // nota\n;")
    assert TokenType.ESPACIO not in [t.type for t in r.tokens]
    assert [t.type for t in r.all_tokens] == [
        TokenType.TK_CMD, TokenType.ESPACIO, TokenType.COMENTARIO,
        TokenType.ESPACIO, TokenType.TK_DELIM, TokenType.EOF,
    ]
    assert r.all_tokens[2].lexeme == "// nota"


def test_texto_vacio_solo_eof() -> None:
    r = lex("")
    assert [t.type for t in r.all_tokens] == [TokenType.EOF]
    assert (r.tokens[0].line, r.tokens[0].col) == (1, 1)


# --- Candidatos alfanuméricos ----------------------------------------------


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [
        ("SCANS", NO_RECONOCIDA.format("SCANS")),
        ("PORT22", NO_RECONOCIDA.format("PORT22")),
        ("foo", NO_RECONOCIDA.format("foo")),
        ("22abc", "Número mal formado '22abc'"),
        ("12_3", "Número mal formado '12_3'"),
        ("scan", "Las palabras reservadas van en MAYÚSCULAS: 'scan' → 'SCAN'"),
        ("Scan", "Las palabras reservadas van en MAYÚSCULAS: 'Scan' → 'SCAN'"),
        ("SCA", "Palabra reservada incompleta 'SCA'"),
        ("ICE_", "Palabra reservada incompleta 'ICE_'"),
        ("0x", "Dirección hexadecimal incompleta: tras '0x' debe haber al menos "
               "un dígito hexadecimal"),
        ("0xFG", "Carácter 'G' no válido en dirección hexadecimal "
                 "(solo 0-9, a-f, A-F)"),
        ("0x_1", "Carácter '_' no válido en dirección hexadecimal "
                 "(solo 0-9, a-f, A-F)"),
        ("0xA_", "Carácter '_' no válido en dirección hexadecimal "
                 "(solo 0-9, a-f, A-F)"),
        ("0X1F", "Número mal formado '0X1F'"),
    ],
)
def test_candidato_invalido_un_solo_error(texto: str, mensaje: str) -> None:
    r = lex(texto)
    assert [e.message for e in r.errors] == [mensaje]
    assert r.errors[0].length == len(texto)
    assert [t.type for t in r.tokens] == [TokenType.EOF]


def test_numeros_validos() -> None:
    r = lex("007 0 8080 0xad23d")
    assert [(t.type, t.lexeme) for t in r.tokens[:-1]] == [
        (TokenType.TK_NUM, "007"), (TokenType.TK_NUM, "0"),
        (TokenType.TK_NUM, "8080"), (TokenType.HEX_ADDR, "0xad23d"),
    ]


# --- Cadenas ------------------------------------------------------------------


def test_cadena_vacia() -> None:
    t = lex('""').tokens[0]
    assert t.type is TokenType.STRING and t.lexeme == '""'


def test_cadena_sin_cerrar() -> None:
    r = lex('SCAN "abc\n;')
    assert [e.message for e in r.errors] == [
        "Cadena sin cerrar: falta la comilla de cierre"
    ]
    e = r.errors[0]
    assert (e.line, e.col, e.length) == (1, 6, 4)
    assert [t.type for t in r.tokens] == [
        TokenType.TK_CMD, TokenType.TK_DELIM, TokenType.EOF,
    ]


def test_cadena_sin_cerrar_al_final() -> None:
    assert lex('"abc').errors[0].length == 4


# --- Operadores y símbolos sueltos -------------------------------------------


def test_operadores_completos() -> None:
    assert tipos("-> == > < { } ;")[:-1] == [
        TokenType.TK_OP, TokenType.TK_IGUAL, TokenType.TK_MAYOR,
        TokenType.TK_MENOR, TokenType.TK_IZQ, TokenType.TK_DER,
        TokenType.TK_DELIM,
    ]


def test_operadores_incompletos_lexer() -> None:
    assert mensajes("-") == ["'-' solo no es un token; ¿quisiste escribir '->'?"]
    assert mensajes("=") == ["'=' solo no es un token; ¿quisiste escribir '=='?"]
    assert mensajes("/") == [
        "'/' solo no es un token; ¿quisiste escribir '//' (comentario)?"
    ]


def test_guion_seguido_de_otro_simbolo() -> None:
    assert len(lex("- >").errors) == 1
    assert tipos("- >") == [TokenType.TK_MAYOR, TokenType.EOF]


def test_punto() -> None:
    assert mensajes(".") == [
        "El símbolo '.' pertenece al alfabeto pero no forma ningún token"
    ]


# --- Unicode ------------------------------------------------------------------


@pytest.mark.parametrize("c", ["–", "—", "−"])
def test_guiones_tipograficos(c: str) -> None:
    assert mensajes(c) == [
        f"El símbolo '{c}' no es el guion '-'; el operador de flujo se escribe "
        "'->' (¿pegaste el texto desde Word?)"
    ]


@pytest.mark.parametrize("c", ["“", "”"])
def test_comillas_tipograficas(c: str) -> None:
    assert mensajes(c) == ['Comillas tipográficas no válidas; usa comillas rectas "']


@pytest.mark.parametrize("c", ["@", "#", "ñ", "é", "€", "'"])
def test_simbolo_ajeno(c: str) -> None:
    assert mensajes(c) == [f"Símbolo '{c}' no pertenece al alfabeto de NetRunner"]


def test_unicode_dentro_de_cadena_y_comentario() -> None:
    r = lex('"ñandú €" // comentario con “comillas”')
    assert not r.errors
    assert r.tokens[0].lexeme == '"ñandú €"'


def test_letra_unicode_corta_candidato() -> None:
    r = lex("SCANñ")
    assert r.tokens[0].lexeme == "SCAN"
    assert len(r.errors) == 1 and r.errors[0].col == 5


# --- Posiciones ---------------------------------------------------------------


def test_posiciones() -> None:
    scan, ports, delim, eof = lex("SCAN\n\tPORTS ;\n").tokens
    assert (scan.line, scan.col) == (1, 1)
    assert (ports.line, ports.col) == (2, 2)  # el tab cuenta una columna
    assert (delim.line, delim.col) == (2, 8)
    assert (eof.line, eof.col) == (3, 1)


def test_eof_justo_despues_del_ultimo_caracter() -> None:
    eof = lex("SCAN;").tokens[-1]
    assert (eof.line, eof.col) == (1, 6)


def test_posicion_de_error() -> None:
    e = lex("SCAN\n  @").errors[0]
    assert (e.kind, e.line, e.col, e.length) == ("LEXICO", 2, 3, 1)


# --- after_lex_error ---------------------------------------------------------


def test_after_lex_error() -> None:
    r = lex("SCAN @ # PORTS ; DATA")
    assert [(t.lexeme, t.after_lex_error) for t in r.tokens] == [
        ("SCAN", False), ("PORTS", True), (";", False),
        ("DATA", False), ("", False),
    ]
    assert all(not t.after_lex_error for t in r.all_tokens
               if t.type is TokenType.ESPACIO)


def test_after_lex_error_en_eof() -> None:
    assert lex("SCAN @").tokens[-1].after_lex_error is True


def test_lexema_invalido_no_produce_token() -> None:
    assert tipos("scan") == [TokenType.EOF]


# --- Trazas -------------------------------------------------------------------


def test_traza_palabra_reservada() -> None:
    t = lex("PORTS").tokens[0]
    assert t.family == "AFD palabras reservadas (Tabla 1)"
    assert t.trace[0] == ("q0", "P", "P")
    assert t.accept_state == "PORTS"
    assert len(t.trace) == 5


def test_traza_operador() -> None:
    t = lex(">").tokens[0]
    assert t.trace == (("q0", ">", "q7"),)
    assert t.accept_state == "q7"


def test_trazas_de_todas_las_familias() -> None:
    r = lex('0xA "s" -> // c\n')
    estados = {t.type: (t.family, t.accept_state) for t in r.all_tokens[:-1]}
    assert estados[TokenType.HEX_ADDR] == ("AFD enteros y hexadecimales (Tabla 2)", "q4")
    assert estados[TokenType.STRING] == ("AFD cadenas de texto (Tabla 3)", "q6")
    assert estados[TokenType.TK_OP] == ("AFD operadores y delimitadores (Tabla 4)", "q11")
    assert estados[TokenType.COMENTARIO] == ("AFD comentarios y espacios (Tabla 5)", "q16")
    assert estados[TokenType.ESPACIO] == ("AFD comentarios y espacios (Tabla 5)", "q17")
    for t in r.all_tokens[:-1]:
        assert "".join(c for _, c, _ in t.trace) == t.lexeme
