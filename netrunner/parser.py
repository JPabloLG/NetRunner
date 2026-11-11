"""Analizador sintáctico predictivo LL(1) por descenso recursivo.

Implementa la gramática G2 del documento (reglas R1-R28). Cada no terminal
tiene un método ``_nombre``. Las decisiones se toman solo con el token actual
(``self.tok.terminal``) y los conjuntos FIRST/FOLLOW calculados en
``grammar.py``; nunca hay retroceso.

Los no terminales primados recursivos por la derecha (``<lista_instr'>``,
``<secuencia'>``) se analizan con bucles ``while``, pero el árbol conserva la
estructura anidada de la derivación (con sus nodos primados y ε).

Ante un error se usa recuperación en modo pánico (nivel instrucción y nivel
programa). Si hubo algún error, el árbol resultante es None.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NoReturn

from netrunner.diagnostics import SINTACTICO, Diagnostic
from netrunner.grammar import (
    END,
    LL1_GRAMMAR,
    compute_first,
    compute_follow,
    terminals,
)
from netrunner.tokens import Token, TokenType
from netrunner.tree import Node, epsilon, leaf

MAX_ERRORS = 100

_FIRST = compute_first(LL1_GRAMMAR)
_FOLLOW = compute_follow(LL1_GRAMMAR, "<programa>", _FIRST)
# Orden fijo de terminales para que los mensajes sean deterministas.
_ORDEN = terminals(LL1_GRAMMAR) + [END]


def _ordenados(simbolos: set[str]) -> list[str]:
    return [t for t in _ORDEN if t in simbolos]


FIRST_INSTRUCCION: list[str] = _ordenados(_FIRST["<instruccion>"])
FIRST_SECUENCIA: list[str] = _ordenados(_FIRST["<secuencia>"])  # ACC
FOLLOW_RESTO_IF: list[str] = _ordenados(_FOLLOW["<resto_if>"])

# R11-R18: <accion> ::= primera palabra + resto. Se toman de LL1_GRAMMAR,
# así que la gramática no se repite a mano.
ACCIONES: dict[str, list[str]] = {
    derecha[0]: derecha[1:] for izquierda, derecha in LL1_GRAMMAR
    if izquierda == "<accion>"
}

_DESCRIPCIONES = {
    "HEX_ADDR": "una dirección hexadecimal",
    "NUM": "un número entero",
    "STRING": "una cadena entre comillas",
    END: "fin de archivo",
}

_AUXILIARES = (TokenType.ESPACIO, TokenType.COMENTARIO)


class ParseError(Exception):
    """Error sintáctico; lo capturan los puntos de recuperación."""


@dataclass
class ParseResult:
    """Resultado del análisis: árbol (None si hubo errores) y diagnósticos."""

    tree: Node | None
    errors: list[Diagnostic] = field(default_factory=list)


def describe_expected(expected: set[str]) -> str:
    """Texto legible del conjunto de terminales esperados.

    Si están los nueve de FIRST(instruccion) se resumen como "una instrucción".
    """
    partes: list[str] = []
    resto = set(expected)
    if set(FIRST_INSTRUCCION) <= resto:
        partes.append("una instrucción")
        resto -= set(FIRST_INSTRUCCION)
    for t in _ordenados(resto):
        partes.append(_DESCRIPCIONES.get(t, f"'{t}'"))
    if len(partes) == 1:
        return partes[0]
    return ", ".join(partes[:-1]) + " o " + partes[-1]


def describe_found(token: Token) -> str:
    """Texto del token encontrado: 'lexema' o fin de archivo."""
    if token.type is TokenType.EOF:
        return "fin de archivo"
    return f"'{token.lexeme}'"


class Parser:
    """Analizador sintáctico LL(1) por descenso recursivo."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = [t for t in tokens if t.type not in _AUXILIARES]
        if not self.tokens or self.tokens[-1].type is not TokenType.EOF:
            ultimo = self.tokens[-1] if self.tokens else None
            linea = ultimo.line if ultimo else 1
            col = ultimo.col + ultimo.length if ultimo else 1
            self.tokens.append(Token(TokenType.EOF, "", linea, col, (), "Fin de entrada"))
        self.pos = 0
        self.expected: set[str] = set()
        self.errors: list[Diagnostic] = []
        self._posiciones_con_error: set[tuple[int, int]] = set()

    # ------------------------------------------------------------------
    # Mecanismo básico
    # ------------------------------------------------------------------

    @property
    def tok(self) -> Token:
        """Token actual (lookahead)."""
        return self.tokens[self.pos]

    def at_eof(self) -> bool:
        return self.tok.type is TokenType.EOF

    def advance(self) -> Token:
        """Consume el token actual y vacía ``expected``."""
        token = self.tok
        if not self.at_eof():
            self.pos += 1
        self.expected.clear()
        return token

    def check(self, t: str) -> bool:
        """True si el token actual es ``t``; si no, anota ``t`` como esperado."""
        if self.tok.terminal == t:
            return True
        self.expected.add(t)
        return False

    def check_any(self, opciones: list[str]) -> bool:
        """``check`` sobre varios terminales (anota todos si ninguno coincide)."""
        return any(self.check(t) for t in opciones)

    def expect(self, t: str) -> Node:
        """Consume ``t`` y devuelve su hoja, o registra el error y lanza ParseError."""
        if self.check(t):
            return leaf(self.advance())
        self.fail()

    def fail(self) -> NoReturn:
        """Registra el error con los terminales esperados y lanza ParseError."""
        self.report()
        raise ParseError

    def report(self) -> None:
        """Registra un diagnóstico en la posición del token actual."""
        tok = self.tok
        posicion = (tok.line, tok.col)
        if posicion in self._posiciones_con_error or len(self.errors) >= MAX_ERRORS:
            return
        self._posiciones_con_error.add(posicion)
        mensaje = (f"Se esperaba {describe_expected(self.expected)}, "
                   f"pero se encontró {describe_found(tok)}")
        if tok.after_lex_error:
            mensaje += " (posible consecuencia de un error léxico anterior)"
        self.errors.append(
            Diagnostic(SINTACTICO, tok.line, tok.col, max(tok.length, 1), mensaje)
        )

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------

    def parse(self) -> ParseResult:
        """Analiza toda la entrada."""
        raiz = self._programa()
        return ParseResult(None if self.errors else raiz, self.errors)

    # ------------------------------------------------------------------
    # Recuperación en modo pánico
    # ------------------------------------------------------------------

    def _instruccion_segura(self) -> Node:
        """<instruccion> con recuperación: descarta hasta ';', '}', FIRST(instruccion) o EOF."""
        inicio = self.pos
        try:
            return self._instruccion()
        except ParseError:
            self._sincronizar_instruccion(inicio)
            return Node("<instruccion>")

    def _sincronizar_instruccion(self, inicio: int) -> None:
        while not self.at_eof():
            t = self.tok.terminal
            if t == ";":
                self.advance()
                break
            if t == "}" or t in FIRST_INSTRUCCION:
                if self.pos == inicio and t != "}":
                    self.advance()  # garantiza progreso
                    continue
                break
            self.advance()
        self.expected.clear()

    # ------------------------------------------------------------------
    # Un método por no terminal de G2
    # ------------------------------------------------------------------

    def _programa(self) -> Node:
        """R1. <programa> ::= TARGET NODE HEX_ADDR <bloque>"""
        nodo = Node("<programa>")
        try:
            for t in ("TARGET", "NODE", "HEX_ADDR"):
                nodo.children.append(self.expect(t))
        except ParseError:
            # Modo pánico: se descarta hasta '{' para analizar el bloque igual.
            while not self.at_eof() and self.tok.terminal != "{":
                self.advance()
            self.expected.clear()
            if self.at_eof():
                return nodo
        try:
            nodo.children.append(self._bloque())
        except ParseError:
            return nodo
        # Después del programa solo puede venir el fin de archivo ($).
        if not self.check(END):
            self.report()
        return nodo

    def _bloque(self) -> Node:
        """R2. <bloque> ::= { <lista_instr> }"""
        abre = self.expect("{")
        lista = self._lista_instr()
        return Node("<bloque>", [abre, lista, self.expect("}")])

    def _lista_instr(self) -> Node:
        """R3. <lista_instr> ::= <instruccion> <lista_instr'>
           R4-R5. <lista_instr'> ::= <instruccion> <lista_instr'> | ε   (bucle)"""
        nodo = Node("<lista_instr>", [self._instruccion_segura()])
        padre = nodo
        while True:
            if self.check_any(FIRST_INSTRUCCION):
                aux = Node("<lista_instr'>", [self._instruccion_segura()])
                padre.children.append(aux)
                padre = aux
            elif self.check("}") or self.at_eof():
                # R5 (ε); si es EOF, el expect('}') de <bloque> informará el error.
                padre.children.append(Node("<lista_instr'>", [epsilon()]))
                return nodo
            else:
                # Basura dentro del bloque: error y recuperación de instrucción.
                self.report()
                self._sincronizar_instruccion(self.pos)

    def _instruccion(self) -> Node:
        """R6-R7. <instruccion> ::= <secuencia> ; | <condicional>"""
        if self.check_any(FIRST_SECUENCIA):
            secuencia = self._secuencia()
            return Node("<instruccion>", [secuencia, self.expect(";")])
        if self.check("IF"):
            return Node("<instruccion>", [self._condicional()])
        self.fail()

    def _secuencia(self) -> Node:
        """R8. <secuencia> ::= <accion> <secuencia'>
           R9-R10. <secuencia'> ::= -> <accion> <secuencia'> | ε   (bucle)"""
        nodo = Node("<secuencia>", [self._accion()])
        padre = nodo
        while True:
            if self.check("->"):
                flecha = self.expect("->")
                aux = Node("<secuencia'>", [flecha, self._accion()])
                padre.children.append(aux)
                padre = aux
            elif self.check(";"):
                padre.children.append(Node("<secuencia'>", [epsilon()]))
                return nodo
            else:
                self.fail()

    def _accion(self) -> Node:
        """R11-R18. <accion> ::= SCAN PORTS | CONNECT PORT NUM | BYPASS FIREWALL | ..."""
        for primero, resto in ACCIONES.items():
            if self.check(primero):
                hojas = [self.expect(primero)] + [self.expect(t) for t in resto]
                return Node("<accion>", hojas)
        self.fail()

    def _condicional(self) -> Node:
        """R19. <condicional> ::= IF <condicion> THEN <bloque> <resto_if>"""
        si = self.expect("IF")
        condicion = self._condicion()
        entonces = self.expect("THEN")
        bloque = self._bloque()
        return Node("<condicional>", [si, condicion, entonces, bloque,
                                      self._resto_if()])

    def _resto_if(self) -> Node:
        """R20-R21. <resto_if> ::= ELSE <bloque> | ε"""
        if self.check("ELSE"):
            sino = self.expect("ELSE")
            return Node("<resto_if>", [sino, self._bloque()])
        if self.check_any(FOLLOW_RESTO_IF):
            return Node("<resto_if>", [epsilon()])
        self.fail()

    def _condicion(self) -> Node:
        """R22-R23. <condicion> ::= ICE_LEVEL <op_rel> NUM | FIREWALL == <estado>"""
        if self.check("ICE_LEVEL"):
            hoja = self.expect("ICE_LEVEL")
            op_rel = self._op_rel()
            return Node("<condicion>", [hoja, op_rel, self.expect("NUM")])
        if self.check("FIREWALL"):
            hoja = self.expect("FIREWALL")
            igual = self.expect("==")
            return Node("<condicion>", [hoja, igual, self._estado()])
        self.fail()

    def _op_rel(self) -> Node:
        """R24-R26. <op_rel> ::= > | < | =="""
        for t in (">", "<", "=="):
            if self.check(t):
                return Node("<op_rel>", [self.expect(t)])
        self.fail()

    def _estado(self) -> Node:
        """R27-R28. <estado> ::= ACTIVE | INACTIVE"""
        for t in ("ACTIVE", "INACTIVE"):
            if self.check(t):
                return Node("<estado>", [self.expect(t)])
        self.fail()
