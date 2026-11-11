"""Modelos de tokens del lenguaje NetRunner DSL."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TokenType(Enum):
    """Categorías léxicas reconocidas por el analizador léxico."""

    TK_CMD = "TK_CMD"
    TK_NUM = "TK_NUM"
    TK_OP = "TK_OP"
    TK_DELIM = "TK_DELIM"
    HEX_ADDR = "HEX_ADDR"
    TK_IZQ = "TK_IZQ"
    TK_DER = "TK_DER"
    TK_MAYOR = "TK_MAYOR"
    TK_MENOR = "TK_MENOR"
    TK_IGUAL = "TK_IGUAL"
    STRING = "STRING"
    COMENTARIO = "COMENTARIO"
    ESPACIO = "ESPACIO"
    EOF = "EOF"


# Las 23 palabras reservadas del lenguaje (token TK_CMD).
RESERVED_WORDS: tuple[str, ...] = (
    "TARGET", "NODE", "IF", "THEN", "ELSE", "SCAN", "PORTS", "CONNECT",
    "PORT", "BYPASS", "ICE_LEVEL", "DISABLE", "FIREWALL", "ACTIVE",
    "INACTIVE", "INJECT", "PAYLOAD", "EXECUTE", "SCRIPT", "EXFIL", "DATA",
    "CLEAR", "LOGS",
)

# Símbolo terminal de la gramática para cada tipo de token.
# TK_CMD no aparece porque su terminal es el propio lexema.
# COMENTARIO y ESPACIO son auxiliares: el parser los descarta, pero se les
# da un nombre propio para poder mostrarlos en la tabla de tokens.
_TERMINALES: dict[TokenType, str] = {
    TokenType.TK_IZQ: "{",
    TokenType.TK_DER: "}",
    TokenType.TK_DELIM: ";",
    TokenType.TK_OP: "->",
    TokenType.TK_MAYOR: ">",
    TokenType.TK_MENOR: "<",
    TokenType.TK_IGUAL: "==",
    TokenType.HEX_ADDR: "HEX_ADDR",
    TokenType.TK_NUM: "NUM",  # en G2 el terminal se llama NUM
    TokenType.STRING: "STRING",
    TokenType.EOF: "$",
    TokenType.COMENTARIO: "COMENTARIO",
    TokenType.ESPACIO: "ESPACIO",
}


@dataclass(frozen=True)
class Token:
    """Unidad léxica producida por el analizador léxico.

    Atributos:
        type: categoría léxica del token.
        lexeme: texto exacto leído del código fuente.
        line: línea donde inicia el token (desde 1).
        col: columna donde inicia el token (desde 1).
        trace: recorrido del AFD como tuplas (estado, símbolo, destino).
        family: familia de AFD que reconoció el token.
        after_lex_error: True si el token aparece después de un error léxico.
    """

    type: TokenType
    lexeme: str
    line: int
    col: int
    trace: tuple[tuple[str, str, str], ...]
    family: str
    after_lex_error: bool = False

    @property
    def length(self) -> int:
        """Longitud del lexema en caracteres."""
        return len(self.lexeme)

    @property
    def accept_state(self) -> str | None:
        """Estado de aceptación del AFD que reconoció el token (None en EOF)."""
        return self.trace[-1][2] if self.trace else None

    @property
    def terminal(self) -> str:
        """Símbolo terminal que representa al token en la gramática."""
        if self.type is TokenType.TK_CMD:
            return self.lexeme
        return _TERMINALES[self.type]
