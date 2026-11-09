"""Analizador sintáctico predictivo LL(1) por descenso recursivo.

Cada no terminal de ``LL1_GRAMMAR`` tiene un método ``_nombre``. Las
decisiones se toman solo con el token actual (``self.tok.terminal``) y los
conjuntos FIRST/FOLLOW calculados en ``grammar.py``; nunca hay retroceso.

Los no terminales recursivos por la derecha (``<programa'>``,
``<lista_sent'>``, ``<secuencia'>``) se analizan con bucles ``while``, pero
el árbol conserva la estructura anidada de la derivación.

Ante un error se usa recuperación en modo pánico (nivel sentencia y nivel
objetivo). Si hubo algún error, el árbol resultante es None.
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


FIRST_SENTENCIA: list[str] = _ordenados(_FIRST["<sentencia>"])
FIRST_SECUENCIA: list[str] = _ordenados(_FIRST["<secuencia>"])
FOLLOW_CONDICIONAL_P: list[str] = _ordenados(_FOLLOW["<condicional'>"])

# <accion> ::= SCAN <accion'> | resto de alternativas (todas terminales).
ACCIONES_SIMPLES: dict[str, list[str]] = {
    "CONNECT": ["PORT", "TK_NUM"],
    "BYPASS": ["FIREWALL"],
    "DISABLE": ["FIREWALL"],
    "INJECT": ["PAYLOAD", "STRING"],
    "EXECUTE": ["SCRIPT", "STRING"],
    "EXFIL": ["DATA"],
    "CLEAR": ["LOGS"],
}

_DESCRIPCIONES = {
    "HEX_ADDR": "una dirección hexadecimal",
    "TK_NUM": "un número entero",
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

    Si están los nueve de FIRST(sentencia) se resumen como "una instrucción".
    """
    partes: list[str] = []
    resto = set(expected)
    if set(FIRST_SENTENCIA) <= resto:
        partes.append("una instrucción")
        resto -= set(FIRST_SENTENCIA)
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

    def _objetivo_seguro(self) -> Node:
        """<objetivo> con recuperación: descarta hasta TARGET o EOF."""
        inicio = self.pos
        try:
            return self._objetivo()
        except ParseError:
            if self.pos == inicio and not self.at_eof():
                self.advance()  # garantiza progreso
            while not self.at_eof() and self.tok.terminal != "TARGET":
                self.advance()
            self.expected.clear()
            return Node("<objetivo>")

    def _sentencia_segura(self) -> Node:
        """<sentencia> con recuperación: descarta hasta ';', '}', FIRST(sentencia) o EOF."""
        inicio = self.pos
        try:
            return self._sentencia()
        except ParseError:
            self._sincronizar_sentencia(inicio)
            return Node("<sentencia>")

    def _sincronizar_sentencia(self, inicio: int) -> None:
        while not self.at_eof():
            t = self.tok.terminal
            if t == ";":
                self.advance()
                break
            if t == "}" or t in FIRST_SENTENCIA:
                if self.pos == inicio and t != "}":
                    self.advance()  # garantiza progreso
                    continue
                break
            self.advance()
        self.expected.clear()

    # ------------------------------------------------------------------
    # Un método por no terminal
    # ------------------------------------------------------------------

    def _programa(self) -> Node:
        """1. <programa> ::= <objetivo> <programa'>
           2. <programa'> ::= <objetivo> <programa'> | ε   (bucle)"""
        nodo = Node("<programa>", [self._objetivo_seguro()])
        padre = nodo
        while True:
            if self.check("TARGET"):
                aux = Node("<programa'>", [self._objetivo_seguro()])
                padre.children.append(aux)
                padre = aux
            elif self.check(END):
                padre.children.append(Node("<programa'>", [epsilon()]))
                return nodo
            else:
                # Token fuera de un objetivo: se descarta hasta TARGET o EOF.
                self.report()
                while not self.at_eof() and self.tok.terminal != "TARGET":
                    self.advance()
                self.expected.clear()

    def _objetivo(self) -> Node:
        """3. <objetivo> ::= TARGET NODE HEX_ADDR <bloque>"""
        return Node("<objetivo>", [
            self.expect("TARGET"),
            self.expect("NODE"),
            self.expect("HEX_ADDR"),
            self._bloque(),
        ])

    def _bloque(self) -> Node:
        """4. <bloque> ::= { <lista_sent> }"""
        abre = self.expect("{")
        lista = self._lista_sent()
        return Node("<bloque>", [abre, lista, self.expect("}")])

    def _lista_sent(self) -> Node:
        """5. <lista_sent> ::= <sentencia> <lista_sent'>
           6. <lista_sent'> ::= <sentencia> <lista_sent'> | ε   (bucle)"""
        nodo = Node("<lista_sent>", [self._sentencia_segura()])
        padre = nodo
        while True:
            if self.check_any(FIRST_SENTENCIA):
                aux = Node("<lista_sent'>", [self._sentencia_segura()])
                padre.children.append(aux)
                padre = aux
            elif self.check("}") or self.at_eof():
                # ε; si es EOF, el expect('}') de <bloque> informará el error.
                padre.children.append(Node("<lista_sent'>", [epsilon()]))
                return nodo
            else:
                # Basura dentro del bloque: error y recuperación de sentencia.
                self.report()
                self._sincronizar_sentencia(self.pos)

    def _sentencia(self) -> Node:
        """7. <sentencia> ::= <secuencia> ; | <condicional>"""
        if self.check_any(FIRST_SECUENCIA):
            secuencia = self._secuencia()
            return Node("<sentencia>", [secuencia, self.expect(";")])
        if self.check("IF"):
            return Node("<sentencia>", [self._condicional()])
        self.fail()

    def _secuencia(self) -> Node:
        """8. <secuencia> ::= <accion> <secuencia'>
           9. <secuencia'> ::= -> <accion> <secuencia'> | ε   (bucle)"""
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
        """10. <accion> ::= SCAN <accion'> | CONNECT PORT TK_NUM | ..."""
        if self.check("SCAN"):
            return Node("<accion>", [self.expect("SCAN"), self._accion_p()])
        for primero, resto in ACCIONES_SIMPLES.items():
            if self.check(primero):
                hojas = [self.expect(primero)] + [self.expect(t) for t in resto]
                return Node("<accion>", hojas)
        self.fail()

    def _accion_p(self) -> Node:
        """11. <accion'> ::= PORTS | PORT TK_NUM"""
        if self.check("PORTS"):
            return Node("<accion'>", [self.expect("PORTS")])
        if self.check("PORT"):
            return Node("<accion'>", [self.expect("PORT"), self.expect("TK_NUM")])
        self.fail()

    def _condicional(self) -> Node:
        """12. <condicional> ::= IF <condicion> THEN <bloque> <condicional'>"""
        si = self.expect("IF")
        condicion = self._condicion()
        entonces = self.expect("THEN")
        bloque = self._bloque()
        return Node("<condicional>", [si, condicion, entonces, bloque,
                                      self._condicional_p()])

    def _condicional_p(self) -> Node:
        """13. <condicional'> ::= ELSE <bloque> | ε"""
        if self.check("ELSE"):
            sino = self.expect("ELSE")
            return Node("<condicional'>", [sino, self._bloque()])
        if self.check_any(FOLLOW_CONDICIONAL_P):
            return Node("<condicional'>", [epsilon()])
        self.fail()

    def _condicion(self) -> Node:
        """14. <condicion> ::= ICE_LEVEL <comp> TK_NUM | FIREWALL == <estado>"""
        if self.check("ICE_LEVEL"):
            hoja = self.expect("ICE_LEVEL")
            comp = self._comp()
            return Node("<condicion>", [hoja, comp, self.expect("TK_NUM")])
        if self.check("FIREWALL"):
            hoja = self.expect("FIREWALL")
            igual = self.expect("==")
            return Node("<condicion>", [hoja, igual, self._estado()])
        self.fail()

    def _comp(self) -> Node:
        """15. <comp> ::= > | < | =="""
        for t in (">", "<", "=="):
            if self.check(t):
                return Node("<comp>", [self.expect(t)])
        self.fail()

    def _estado(self) -> Node:
        """16. <estado> ::= ACTIVE | INACTIVE"""
        for t in ("ACTIVE", "INACTIVE"):
            if self.check(t):
                return Node("<estado>", [self.expect(t)])
        self.fail()
