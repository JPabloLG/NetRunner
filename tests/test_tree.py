"""Pruebas del árbol sintáctico, la simplificación, el layout y las exportaciones."""

import xml.etree.ElementTree as ET

import pytest

from netrunner.lexer import Lexer
from netrunner.parser import Parser
from netrunner.tree import (
    Node,
    frontier,
    preorder,
    simplify,
    to_ascii,
    to_dot,
    to_svg,
)
from netrunner.tree_layout import layout_tree

PROGRAMA = (
    'TARGET NODE 0xad23d {\n'
    '    SCAN PORT 22 -> INJECT PAYLOAD "a\\b";\n'
    '    IF ICE_LEVEL < 3 THEN {\n'
    '        BYPASS FIREWALL;\n'
    '    } ELSE {\n'
    '        CLEAR LOGS;\n'
    '    }\n'
    '}\n'
    'TARGET NODE 0xFF { EXFIL DATA; }\n'
)


def arbol(src: str = PROGRAMA) -> Node:
    lx = Lexer(src).tokenize()
    r = Parser(lx.tokens).parse()
    assert not lx.errors and not r.errors
    assert r.tree is not None
    return r.tree


def lexemas(src: str) -> list[str]:
    return [t.lexeme for t in Lexer(src).tokenize().tokens[:-1]]


def simbolos(raiz: Node) -> list[str]:
    return [n.symbol for n, _ in preorder(raiz)]


# --- Node -------------------------------------------------------------------


def test_propiedades_de_nodo() -> None:
    raiz = arbol()
    assert raiz.symbol == "<programa>" and raiz.label == "<programa>"
    assert not raiz.is_terminal and not raiz.is_epsilon
    hoja = raiz.children[0].children[0]
    assert hoja.symbol == "TK_CMD" and hoja.label == "TARGET" and hoja.is_terminal
    eps = Node("ε")
    assert eps.is_epsilon and eps.label == "ε" and not eps.is_terminal
    assert Node("<a>", [Node("ε"), Node("<b>")]).count() == 3


def test_arbol_completo_conserva_auxiliares_y_epsilon() -> None:
    s = simbolos(arbol())
    for aux in ("<programa'>", "<lista_sent'>", "<secuencia'>", "<accion'>",
                "<condicional'>"):
        assert aux in s
    assert "ε" in s


def test_estructura_anidada_de_lista_sent() -> None:
    raiz = arbol("TARGET NODE 0x1 { SCAN PORTS; CLEAR LOGS; EXFIL DATA; }")
    lista = raiz.children[0].children[3].children[1]
    assert lista.symbol == "<lista_sent>"
    profundidad = 0
    nodo = lista.children[1]
    while nodo.symbol == "<lista_sent'>":
        profundidad += 1
        if nodo.children[0].is_epsilon:
            break
        nodo = nodo.children[1]
    assert profundidad == 3  # dos sentencias más + ε


def test_frontera_igual_a_los_tokens() -> None:
    assert frontier(arbol()) == lexemas(PROGRAMA)


# --- Simplificación -------------------------------------------------------------


def test_simplificacion() -> None:
    raiz = arbol()
    antes = to_ascii(raiz)
    simple = simplify(raiz)
    s = simbolos(simple)
    assert "ε" not in s
    assert not any(x.endswith("'>") for x in s)
    assert frontier(simple) == frontier(raiz)
    assert to_ascii(raiz) == antes  # el original no cambia
    assert simple.count() < raiz.count()
    for nodo, _ in preorder(simple):
        assert nodo.is_terminal or nodo.children


def test_simplificacion_aplana_sentencias() -> None:
    simple = simplify(arbol("TARGET NODE 0x1 { SCAN PORTS; CLEAR LOGS; EXFIL DATA; }"))
    lista = simple.children[0].children[3].children[1]
    assert [h.symbol for h in lista.children] == ["<sentencia>"] * 3


# --- ASCII y DOT ----------------------------------------------------------------


def test_ascii() -> None:
    texto = to_ascii(arbol())
    assert texto.splitlines()[0] == "<programa>"
    assert "├── " in texto and "└── " in texto and "│   " in texto
    assert "TARGET [TK_CMD @1:1]" in texto
    assert "0xad23d [HEX_ADDR @1:13]" in texto


def test_dot() -> None:
    dot = to_dot(arbol())
    assert dot.startswith("digraph arbol {")
    assert dot.rstrip().endswith("}")
    assert "shape=box" in dot
    assert 'shape=ellipse, style=filled, fillcolor="#d3f9d8"' in dot
    assert "shape=plaintext" in dot
    assert r'label="\"a\\b\""' in dot  # comillas y barra escapadas
    raiz = arbol()
    assert dot.count("->") - 1 == raiz.count() - 1  # aristas (+ el lexema '->')


def test_dot_escapa_barra_invertida() -> None:
    dot = to_dot(arbol('TARGET NODE 0x1 { EXECUTE SCRIPT "c:\\x"; }'))
    assert r'label="\"c:\\x\""' in dot


# --- SVG ----------------------------------------------------------------------


@pytest.mark.parametrize("tema", ["light", "dark"])
def test_svg_bien_formado(tema: str) -> None:
    svg = to_svg(arbol(), tema)
    raiz = ET.fromstring(svg)
    ns = "{http://www.w3.org/2000/svg}"
    assert raiz.tag == f"{ns}svg"
    assert "viewBox" in raiz.attrib
    assert raiz.find(f"{ns}title") is not None


def test_svg_colores_tema_claro() -> None:
    svg = to_svg(arbol())
    for color in ("#ffffff", "#444", "#0077aa", "#d3f9d8", "#087f5b", "#111"):
        assert color in svg


def test_svg_tema_invalido() -> None:
    with pytest.raises(ValueError):
        to_svg(arbol(), "azul")


# --- Layout -------------------------------------------------------------------


def _medir(texto: str) -> float:
    return 7.0 * len(texto)


@pytest.mark.parametrize("simplificado", [False, True])
def test_layout_sin_solapamientos(simplificado: bool) -> None:
    raiz = arbol()
    if simplificado:
        raiz = simplify(raiz)
    layout = layout_tree(raiz, _medir)
    assert len(layout.nodes) == raiz.count()
    niveles: dict[int, list] = {}
    for p in layout.nodes:
        niveles.setdefault(p.depth, []).append(p)
        assert p.y_centro == p.depth * (34 + 46) + 34 / 2
    for nodos in niveles.values():
        nodos.sort(key=lambda p: p.x_centro)
        for a, b in zip(nodos, nodos[1:]):
            assert a.x_centro + a.w / 2 <= b.x_centro - b.w / 2 + 1e-9
    for p in layout.nodes:
        assert p.x_centro - p.w / 2 >= -1e-9
        assert p.x_centro + p.w / 2 <= layout.width + 1e-9


def test_layout_padre_centrado_e_hijos_ordenados() -> None:
    layout = layout_tree(arbol(), _medir)
    hijos: dict[int, list] = {}
    for p in layout.nodes:
        if p.indice_padre >= 0:
            hijos.setdefault(p.indice_padre, []).append(p)
    for i, lista in hijos.items():
        xs = [p.x_centro for p in lista]
        assert xs == sorted(xs)
        izq = lista[0].x_centro - lista[0].w / 2
        der = lista[-1].x_centro + lista[-1].w / 2
        padre = layout.nodes[i]
        # El padre está dentro del tramo de sus hijos y cerca de su centro.
        assert izq - 1e-9 <= padre.x_centro <= der + 1e-9


def test_layout_un_solo_nodo() -> None:
    layout = layout_tree(Node("<x>"), _medir)
    assert layout.height == 34
    assert layout.nodes[0].indice_padre == -1


# --- Árboles grandes ------------------------------------------------------------


def test_arbol_profundo_sin_recursion() -> None:
    src = "TARGET NODE 0x1 {\n" + "SCAN PORTS;\n" * 2000 + "}\n"
    raiz = arbol(src)
    assert len(frontier(raiz)) == 5 + 3 * 2000
    simple = simplify(raiz)
    assert frontier(simple) == frontier(raiz)
    assert layout_tree(simple, _medir).width > 0
    assert to_dot(raiz).startswith("digraph")
    ET.fromstring(to_svg(raiz))
