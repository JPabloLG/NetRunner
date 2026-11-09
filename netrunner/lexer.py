"""Analizador léxico de NetRunner basado en los cinco AFD de la Fase 1.

El texto se recorre con un índice. Según el primer carácter se elige la
familia de AFD (los símbolos iniciales de las familias son disjuntos, así
que la elección es única) y se aplica máxima coincidencia con ``run_afd``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from netrunner.afd_tables import (
    BLANK,
    CANDIDATE_CHARS,
    DIGITS,
    KEYWORD_FAMILY,
    NUM_FAMILY,
    OPS_FAMILY,
    STR_FAMILY,
    WS_FAMILY,
    AFDFamily,
    RunResult,
)
from netrunner.diagnostics import LEXICO, Diagnostic
from netrunner.tokens import RESERVED_WORDS, Token, TokenType

FAMILIA_EOF = "Fin de entrada"

# Símbolos que suelen llegar al pegar texto desde un procesador de textos.
GUIONES_TIPOGRAFICOS: frozenset[str] = frozenset("‐‑‒–—−")
COMILLAS_TIPOGRAFICAS: frozenset[str] = frozenset("“”„‟‘’")


@dataclass
class LexResult:
    """Resultado del análisis léxico.

    Atributos:
        tokens: tokens significativos (sin ESPACIO ni COMENTARIO), con EOF al final.
        all_tokens: todos los tokens, incluidos ESPACIO y COMENTARIO, con EOF al final.
        errors: diagnósticos léxicos encontrados.
    """

    tokens: list[Token] = field(default_factory=list)
    all_tokens: list[Token] = field(default_factory=list)
    errors: list[Diagnostic] = field(default_factory=list)


class Lexer:
    """Convierte el código fuente en una secuencia de tokens."""

    def __init__(self, source: str) -> None:
        self.source = source
        self._lines, self._cols = self._calcular_posiciones(source)

    @staticmethod
    def _calcular_posiciones(source: str) -> tuple[list[int], list[int]]:
        """Línea y columna (desde 1) de cada índice, incluido el fin del texto."""
        lines: list[int] = []
        cols: list[int] = []
        line, col = 1, 1
        for c in source:
            lines.append(line)
            cols.append(col)
            if c == "\n":
                line, col = line + 1, 1
            else:
                col += 1
        lines.append(line)
        cols.append(col)
        return lines, cols

    # ------------------------------------------------------------------
    # Algoritmo principal
    # ------------------------------------------------------------------

    def tokenize(self) -> LexResult:
        """Recorre todo el texto y devuelve tokens y errores léxicos."""
        self._result = LexResult()
        self._pending_error = False
        text = self.source
        i = 0
        while i < len(text):
            c = text[i]
            if c in BLANK:
                i = self._leer_espacio(i)
            elif c == "/":
                i = self._leer_comentario(i)
            elif c == '"':
                i = self._leer_cadena(i)
            elif c in OPS_FAMILY.table["q0"]:
                i = self._leer_operador(i)
            elif c in CANDIDATE_CHARS:
                i = self._leer_candidato(i)
            else:
                self._error_simbolo(i)
                i += 1

        n = len(text)
        self._emitir(Token(TokenType.EOF, "", self._lines[n], self._cols[n],
                           (), FAMILIA_EOF))
        return self._result

    # ------------------------------------------------------------------
    # Casos
    # ------------------------------------------------------------------

    def _leer_espacio(self, i: int) -> int:
        r = WS_FAMILY.run(self.source, i)
        self._emitir_aceptado(r, WS_FAMILY)
        return r.accept_pos

    def _leer_comentario(self, i: int) -> int:
        r = WS_FAMILY.run(self.source, i)
        if r.accepted:
            self._emitir_aceptado(r, WS_FAMILY)
            return r.accept_pos
        self._error(i, 1, "'/' solo no es un token; ¿quisiste escribir '//' (comentario)?")
        return i + 1

    def _leer_cadena(self, i: int) -> int:
        r = STR_FAMILY.run(self.source, i)
        if r.accepted:
            self._emitir_aceptado(r, STR_FAMILY)
            return r.accept_pos
        # Sin cierre: se consume hasta antes del salto de línea (o fin del texto).
        self._error(i, r.stop_pos - i, "Cadena sin cerrar: falta la comilla de cierre")
        return r.stop_pos

    def _leer_operador(self, i: int) -> int:
        r = OPS_FAMILY.run(self.source, i)
        if r.accepted:
            self._emitir_aceptado(r, OPS_FAMILY)
            return r.accept_pos
        if self.source[i] == "-":
            mensaje = "'-' solo no es un token; ¿quisiste escribir '->'?"
        else:
            mensaje = "'=' solo no es un token; ¿quisiste escribir '=='?"
        self._error(i, 1, mensaje)
        return i + 1

    def _leer_candidato(self, i: int) -> int:
        """Extrae el candidato máximo [A-Za-z0-9_] y lo valida completo.

        Un candidato inválido produce un único error y nunca se divide en
        varios tokens.
        """
        text = self.source
        j = i
        while j < len(text) and text[j] in CANDIDATE_CHARS:
            j += 1
        lexema = text[i:j]

        familia = NUM_FAMILY if lexema[0] in DIGITS else KEYWORD_FAMILY
        r = familia.run(text, i)
        if r.accepted and r.accept_pos == j:
            self._emitir_aceptado(r, familia)
        elif familia is NUM_FAMILY:
            self._error(i, j - i, self._mensaje_numero(lexema, r, j))
        else:
            self._error(i, j - i, self._mensaje_palabra(lexema, r, j))
        return j

    def _mensaje_numero(self, lexema: str, r: RunResult, fin: int) -> str:
        """El mensaje se decide por el estado en que se detuvo el AFD (Tabla 2).

        - Murió en q3 al final del candidato: se leyó "0x" y nada más.
        - Murió en q3 o q4 antes del final: el carácter siguiente no es
          hexadecimal.
        - En cualquier otro caso, el número está mal formado.
        """
        if r.dead_state in ("q3", "q4"):
            if r.stop_pos == fin:
                return ("Dirección hexadecimal incompleta: tras '0x' debe haber "
                        "al menos un dígito hexadecimal")
            return (f"Carácter '{self.source[r.stop_pos]}' no válido en dirección "
                    "hexadecimal (solo 0-9, a-f, A-F)")
        return f"Número mal formado '{lexema}'"

    @staticmethod
    def _mensaje_palabra(lexema: str, r: RunResult, fin: int) -> str:
        """Orden de decisión: MAYÚSCULAS, incompleta (el trie leyó todo el
        candidato sin morir, pero terminó en un estado que no es final) y,
        por último, palabra no reconocida."""
        mayus = lexema.upper()
        if mayus in RESERVED_WORDS and mayus != lexema:
            return (f"Las palabras reservadas van en MAYÚSCULAS: "
                    f"'{lexema}' → '{mayus}'")
        if r.stop_pos == fin:
            return f"Palabra reservada incompleta '{lexema}'"
        return (f"Palabra no reconocida '{lexema}': NetRunner solo admite sus "
                "23 palabras reservadas (no hay identificadores)")

    def _error_simbolo(self, i: int) -> None:
        c = self.source[i]
        if c == ".":
            mensaje = "El símbolo '.' pertenece al alfabeto pero no forma ningún token"
        elif c in GUIONES_TIPOGRAFICOS:
            mensaje = (f"El símbolo '{c}' no es el guion '-'; el operador de flujo "
                       "se escribe '->' (¿pegaste el texto desde Word?)")
        elif c in COMILLAS_TIPOGRAFICAS:
            mensaje = 'Comillas tipográficas no válidas; usa comillas rectas "'
        else:
            mensaje = f"Símbolo '{c}' no pertenece al alfabeto de NetRunner"
        self._error(i, 1, mensaje)

    # ------------------------------------------------------------------
    # Emisión de tokens y errores
    # ------------------------------------------------------------------

    def _emitir_aceptado(self, r: RunResult, familia: AFDFamily) -> None:
        """Crea el token del lexema aceptado (retrocediendo a accept_pos)."""
        assert r.token_name is not None
        self._emitir(Token(
            type=TokenType[r.token_name],
            lexeme=self.source[r.start:r.accept_pos],
            line=self._lines[r.start],
            col=self._cols[r.start],
            trace=r.accepted_trace,
            family=familia.name,
        ))

    def _emitir(self, token: Token) -> None:
        """Agrega el token y marca after_lex_error en el primer token
        significativo posterior a un error. ESPACIO y COMENTARIO no consumen
        la marca."""
        auxiliar = token.type in (TokenType.ESPACIO, TokenType.COMENTARIO)
        if not auxiliar and self._pending_error:
            token = Token(token.type, token.lexeme, token.line, token.col,
                          token.trace, token.family, after_lex_error=True)
            self._pending_error = False
        self._result.all_tokens.append(token)
        if not auxiliar:
            self._result.tokens.append(token)

    def _error(self, i: int, length: int, message: str) -> None:
        self._result.errors.append(
            Diagnostic(LEXICO, self._lines[i], self._cols[i], length, message)
        )
        self._pending_error = True
