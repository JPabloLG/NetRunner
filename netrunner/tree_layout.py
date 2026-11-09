"""Cálculo de posiciones para dibujar el árbol sintáctico.

No depende de Tkinter: recibe una función ``text_width`` que mide el ancho
de un texto (la GUI usa la fuente real; el SVG usa una estimación).

Algoritmo:
  1. Ancho de cada subárbol = max(ancho de su caja,
     suma de los anchos de sus hijos + separaciones).
  2. Cada subárbol recibe un tramo horizontal propio; los hijos se reparten
     de izquierda a derecha dentro del tramo del padre.
  3. El padre queda centrado sobre el tramo de sus hijos.
  4. El borde superior de una caja está en profundidad * (box_h + v_gap).

Como los tramos de subárboles hermanos no se cruzan, las cajas de un mismo
nivel nunca se solapan. Todo es iterativo para soportar árboles profundos.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from netrunner.tree import Node

PADDING_X = 10.0  # espacio a cada lado del texto dentro de la caja
MIN_BOX_W = 34.0


@dataclass(frozen=True)
class PlacedNode:
    """Nodo con posición.

    Atributos:
        x_centro: coordenada x del centro de la caja.
        y_centro: coordenada y del centro de la caja.
        w: ancho de la caja.
        h: alto de la caja.
        node: nodo del árbol.
        indice_padre: índice del padre en ``Layout.nodes`` (-1 en la raíz).
        depth: profundidad (0 en la raíz).
    """

    x_centro: float
    y_centro: float
    w: float
    h: float
    node: Node
    indice_padre: int
    depth: int


@dataclass(frozen=True)
class Layout:
    """Resultado del layout: nodos en preorden y tamaño total."""

    nodes: list[PlacedNode]
    width: float
    height: float


def layout_tree(
    root: Node,
    text_width: Callable[[str], float],
    h_gap: float = 14,
    v_gap: float = 46,
    box_h: float = 34,
) -> Layout:
    """Calcula la posición de cada nodo del árbol."""
    # 1. Preorden con índice del padre y profundidad.
    nodos: list[Node] = []
    padres: list[int] = []
    profundidades: list[int] = []
    hijos: list[list[int]] = []
    pila: list[tuple[Node, int, int]] = [(root, -1, 0)]
    while pila:
        nodo, padre, prof = pila.pop()
        indice = len(nodos)
        nodos.append(nodo)
        padres.append(padre)
        profundidades.append(prof)
        hijos.append([])
        if padre >= 0:
            hijos[padre].append(indice)
        for hijo in reversed(nodo.children):
            pila.append((hijo, indice, prof + 1))

    n = len(nodos)
    cajas = [max(text_width(nd.label) + 2 * PADDING_X, MIN_BOX_W) for nd in nodos]

    # 2. Ancho de cada subárbol (en preorden inverso los hijos van primero).
    def tramo_hijos(i: int) -> float:
        return sum(sub[c] for c in hijos[i]) + h_gap * (len(hijos[i]) - 1)

    sub = [0.0] * n
    for i in range(n - 1, -1, -1):
        sub[i] = max(cajas[i], tramo_hijos(i)) if hijos[i] else cajas[i]

    # 3. Borde izquierdo de cada subárbol, de arriba hacia abajo.
    izquierda = [0.0] * n
    for i in range(n):
        if not hijos[i]:
            continue
        x = izquierda[i] + (sub[i] - tramo_hijos(i)) / 2
        for c in hijos[i]:
            izquierda[c] = x
            x += sub[c] + h_gap

    colocados = [
        PlacedNode(
            x_centro=izquierda[i] + sub[i] / 2,
            y_centro=profundidades[i] * (box_h + v_gap) + box_h / 2,
            w=cajas[i],
            h=box_h,
            node=nodos[i],
            indice_padre=padres[i],
            depth=profundidades[i],
        )
        for i in range(n)
    ]
    max_prof = max(profundidades)
    alto = (max_prof + 1) * box_h + max_prof * v_gap
    return Layout(colocados, sub[0], alto)
