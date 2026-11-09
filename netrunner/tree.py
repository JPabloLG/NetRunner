"""Árbol sintáctico de NetRunner y sus representaciones (ASCII, DOT, SVG).

Todas las funciones que recorren el árbol son iterativas (pila explícita):
un programa con miles de sentencias genera cadenas de nodos auxiliares muy
profundas y la recursión de Python se agotaría.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

from netrunner.tokens import Token
from netrunner.tree_layout import layout_tree

EPSILON = "ε"


@dataclass
class Node:
    """Nodo del árbol sintáctico.

    - No terminal: ``symbol`` es ``"<programa>"``, ``token`` es None.
    - Hoja terminal: ``symbol`` es el tipo del token (``"TK_CMD"``) y
      ``token`` guarda el token leído.
    - Hoja vacía: ``symbol`` es ``"ε"``.
    """

    symbol: str
    children: list[Node] = field(default_factory=list)
    token: Token | None = None

    @property
    def is_terminal(self) -> bool:
        """True si es una hoja con token."""
        return self.token is not None

    @property
    def is_epsilon(self) -> bool:
        """True si es una hoja ε."""
        return self.symbol == EPSILON

    @property
    def is_auxiliary(self) -> bool:
        """True si es un no terminal auxiliar de la gramática LL(1) (``<x'>``)."""
        return self.symbol.startswith("<") and self.symbol.endswith("'>")

    @property
    def label(self) -> str:
        """Nombre del no terminal, lexema del terminal o ε."""
        if self.token is not None:
            return self.token.lexeme
        return self.symbol

    def count(self) -> int:
        """Cantidad de nodos del subárbol (incluido este)."""
        total = 0
        pila: list[Node] = [self]
        while pila:
            nodo = pila.pop()
            total += 1
            pila.extend(nodo.children)
        return total


def epsilon() -> Node:
    """Crea una hoja ε."""
    return Node(EPSILON)


def leaf(token: Token) -> Node:
    """Crea una hoja terminal a partir de un token."""
    return Node(token.type.name, [], token)


def preorder(root: Node) -> list[tuple[Node, int]]:
    """Nodos en preorden (izquierda a derecha) con su profundidad."""
    resultado: list[tuple[Node, int]] = []
    pila: list[tuple[Node, int]] = [(root, 0)]
    while pila:
        nodo, prof = pila.pop()
        resultado.append((nodo, prof))
        for hijo in reversed(nodo.children):
            pila.append((hijo, prof + 1))
    return resultado


def frontier(root: Node) -> list[str]:
    """Lexemas de las hojas terminales de izquierda a derecha."""
    return [n.label for n, _ in preorder(root) if n.is_terminal]


# ---------------------------------------------------------------------------
# Simplificación
# ---------------------------------------------------------------------------


def simplify(root: Node) -> Node:
    """Copia simplificada del árbol (el original no se modifica).

    1. Se eliminan las hojas ε.
    2. Los no terminales auxiliares (``<x'>``) se reemplazan por sus hijos.
    3. Se eliminan los no terminales que quedan sin hijos.

    La frontera del árbol se conserva. Se recorre en postorden: cada nodo
    produce una lista de nodos que lo reemplazan en su padre.
    """
    reemplazos: dict[int, list[Node]] = {}
    pila: list[tuple[Node, bool]] = [(root, False)]
    while pila:
        nodo, hijos_listos = pila.pop()
        if not hijos_listos:
            pila.append((nodo, True))
            for hijo in nodo.children:
                pila.append((hijo, False))
            continue
        if nodo.is_epsilon:
            nuevo: list[Node] = []
        elif nodo.is_terminal:
            nuevo = [Node(nodo.symbol, [], nodo.token)]
        else:
            hijos = [n for h in nodo.children for n in reemplazos.pop(id(h))]
            if nodo.is_auxiliary:
                nuevo = hijos
            elif hijos:
                nuevo = [Node(nodo.symbol, hijos)]
            else:
                nuevo = []
        reemplazos[id(nodo)] = nuevo
    resultado = reemplazos[id(root)]
    return resultado[0] if len(resultado) == 1 else Node(root.symbol, resultado)


# ---------------------------------------------------------------------------
# Representación ASCII
# ---------------------------------------------------------------------------


def _texto_ascii(nodo: Node) -> str:
    if nodo.token is not None:
        t = nodo.token
        return f"{t.lexeme} [{nodo.symbol} @{t.line}:{t.col}]"
    return nodo.symbol


def to_ascii(root: Node) -> str:
    """Árbol jerárquico con ├──, └── y │."""
    lineas: list[str] = []
    # (nodo, prefijo, es_último, es_raíz)
    pila: list[tuple[Node, str, bool, bool]] = [(root, "", True, True)]
    while pila:
        nodo, prefijo, ultimo, raiz = pila.pop()
        if raiz:
            lineas.append(_texto_ascii(nodo))
            prefijo_hijos = ""
        else:
            rama = "└── " if ultimo else "├── "
            lineas.append(prefijo + rama + _texto_ascii(nodo))
            prefijo_hijos = prefijo + ("    " if ultimo else "│   ")
        n = len(nodo.children)
        for i in range(n - 1, -1, -1):
            pila.append((nodo.children[i], prefijo_hijos, i == n - 1, False))
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Graphviz DOT
# ---------------------------------------------------------------------------


def _escapar_dot(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace('"', '\\"')


def to_dot(root: Node) -> str:
    """Árbol en formato DOT de Graphviz."""
    lineas = ["digraph arbol {", "    node [fontname=\"monospace\"];"]
    ids: dict[int, str] = {}
    for i, (nodo, _) in enumerate(preorder(root)):
        ids[id(nodo)] = f"n{i}"
        etiqueta = _escapar_dot(nodo.label)
        if nodo.is_epsilon:
            estilo = "shape=plaintext"
        elif nodo.is_terminal:
            estilo = 'shape=ellipse, style=filled, fillcolor="#d3f9d8"'
        else:
            estilo = "shape=box"
        lineas.append(f'    n{i} [label="{etiqueta}", {estilo}];')
    for nodo, _ in preorder(root):
        for hijo in nodo.children:
            lineas.append(f"    {ids[id(nodo)]} -> {ids[id(hijo)]};")
    lineas.append("}")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "fondo": "#ffffff",
        "linea": "#444",
        "borde_nt": "#0077aa",
        "relleno_nt": "#ffffff",
        "relleno_t": "#d3f9d8",
        "borde_t": "#087f5b",
        "texto": "#111",
    },
    "dark": {
        "fondo": "#1e1e1e",
        "linea": "#aaa",
        "borde_nt": "#4fc3f7",
        "relleno_nt": "#1e1e1e",
        "relleno_t": "#1b4332",
        "borde_t": "#52b788",
        "texto": "#eee",
    },
}

_ANCHO_CARACTER = 7.8  # estimación de ancho de un carácter monoespaciado de 13 px
_MARGEN = 20


def to_svg(root: Node, theme: str = "light") -> str:
    """Árbol como imagen SVG, usando el layout de ``tree_layout``."""
    if theme not in THEMES:
        raise ValueError(f"Tema desconocido: {theme!r} (usa 'light' o 'dark')")
    c = THEMES[theme]
    layout = layout_tree(root, lambda s: len(s) * _ANCHO_CARACTER)
    ancho = layout.width + 2 * _MARGEN
    alto = layout.height + 2 * _MARGEN

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho:.0f}" '
        f'height="{alto:.0f}" viewBox="0 0 {ancho:.0f} {alto:.0f}">',
        "<title>Árbol sintáctico de NetRunner</title>",
        f'<rect width="100%" height="100%" fill="{c["fondo"]}"/>',
        f'<g transform="translate({_MARGEN},{_MARGEN})" '
        'font-family="monospace" font-size="13" text-anchor="middle">',
    ]
    for p in layout.nodes:
        if p.indice_padre >= 0:
            padre = layout.nodes[p.indice_padre]
            partes.append(
                f'<line x1="{padre.x_centro:.1f}" y1="{padre.y_centro + padre.h / 2:.1f}" '
                f'x2="{p.x_centro:.1f}" y2="{p.y_centro - p.h / 2:.1f}" stroke="{c["linea"]}"/>'
            )
    for p in layout.nodes:
        x0, y0 = p.x_centro - p.w / 2, p.y_centro - p.h / 2
        if p.node.is_terminal:
            partes.append(
                f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{p.w:.1f}" height="{p.h:.1f}" '
                f'rx="{p.h / 2:.1f}" fill="{c["relleno_t"]}" stroke="{c["borde_t"]}"/>'
            )
        elif not p.node.is_epsilon:
            partes.append(
                f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{p.w:.1f}" height="{p.h:.1f}" '
                f'rx="4" fill="{c["relleno_nt"]}" stroke="{c["borde_nt"]}"/>'
            )
        partes.append(
            f'<text x="{p.x_centro:.1f}" y="{p.y_centro + 4:.1f}" fill="{c["texto"]}">'
            f"{escape(p.node.label)}</text>"
        )
    partes.append("</g>")
    partes.append("</svg>")
    return "\n".join(partes)
