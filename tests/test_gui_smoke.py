"""Prueba de humo de la interfaz gráfica (se omite si no hay pantalla)."""

import tkinter as tk

import pytest

from netrunner.examples import read_example
from netrunner.gui.panels import NO_TREE_MESSAGE, format_trace
from netrunner.lexer import Lexer

VALIDO = (
    "TARGET NODE 0xad23d {\n"
    "    SCAN PORTS -> EXFIL DATA;\n"
    "    IF ICE_LEVEL > 3 THEN { BYPASS FIREWALL; } ELSE { CLEAR LOGS; }\n"
    "}\n"
)
TRES_ERRORES = (
    "TARGET NODE 0x1 {\n"
    "    SCAN PORTS @;\n"
    "    CONNECT 22;\n"
    "    BYPASS;\n"
    "}\n"
)


@pytest.fixture(scope="module")
def _aplicacion():
    # Una sola ventana para todo el módulo. En Windows con Python 3.14, crear
    # un segundo Tk() después de destruir la aplicación dentro de pytest falla
    # ("Can't find a usable init.tcl"); la aplicación real solo crea uno.
    try:
        root = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"Sin pantalla disponible: {e}")
    root.withdraw()
    from netrunner.gui.app import NetRunnerApp

    aplicacion = NetRunnerApp(root)
    yield aplicacion
    try:
        root.destroy()
    except tk.TclError:
        pass  # ya destruida por test_destruccion


@pytest.fixture
def app(_aplicacion):
    _aplicacion.simplify_var.set(False)
    _aplicacion.clear()
    return _aplicacion


def test_arranque(_aplicacion) -> None:
    """Al iniciar se carga y analiza ok_1_completo.nr automáticamente."""
    texto = read_example("ok_1_completo.nr")
    assert _aplicacion.editor.get_text() == texto
    esperado = "CÓDIGO VÁLIDO" if texto.strip() else "SIN CÓDIGO"
    assert _aplicacion.summary.verdict.cget("text") == esperado


def _filas(tree) -> int:
    return len(tree.get_children(""))


def _ejemplo_o_skip(nombre: str) -> str:
    texto = read_example(nombre)
    if not texto.strip():
        pytest.skip(f"{nombre} está vacío: falta el contenido oficial del ejemplo")
    return texto


def test_creacion_y_analisis_valido(app) -> None:
    assert app.root.title() == "NetRunner Analyzer — Analizador léxico y sintáctico"
    app.editor.set_text(VALIDO)
    app.analyze()
    assert app.tree is not None
    assert _filas(app.derivation.tree) == 1  # raíz <programa>
    assert app.derivation.tree.item(app.derivation.tree.get_children("")[0], "text") \
        == "<programa>"
    assert _filas(app.errors_panel.tree) == 0
    assert app.errors_panel.message.cget("text") == "Sin errores léxicos ni sintácticos."
    assert app.summary.verdict.cget("text") == "CÓDIGO VÁLIDO"
    assert app.notebook.select() == str(app.derivation)
    assert app.status.cget("text").startswith("Análisis correcto:")
    assert _filas(app.tokens_panel.tree) == len(Lexer(VALIDO).tokenize().tokens)
    assert app.canvas_panel.layout is not None


def test_analisis_con_tres_errores(app) -> None:
    app.editor.set_text(TRES_ERRORES)
    app.analyze()
    assert app.tree is None
    assert _filas(app.errors_panel.tree) == 3
    assert app.summary.verdict.cget("text") == "CÓDIGO CON ERRORES"
    assert app.notebook.select() == str(app.errors_panel)
    assert app.status.cget("text") == "Análisis con errores: 1 léxicos, 2 sintácticos."
    assert app.derivation.message.cget("text") == NO_TREE_MESSAGE
    assert app.editor.text.tag_ranges("error")


def test_sin_codigo(app) -> None:
    app.clear()
    assert app.summary.verdict.cget("text") == "SIN CÓDIGO"
    assert _filas(app.tokens_panel.tree) == 0


def test_simplificar_compartido(app) -> None:
    app.editor.set_text(VALIDO)
    app.analyze()
    completo = app.canvas_panel.layout.nodes
    app.simplify_var.set(True)
    assert len(app.canvas_panel.layout.nodes) < len(completo)
    assert app.derivation.root_node is app.canvas_panel.root_node


def test_seleccion_de_token_y_error(app) -> None:
    app.editor.set_text(VALIDO)
    app.analyze()
    app.tokens_panel.tree.selection_set("2")  # HEX_ADDR
    app.root.update()
    assert app.editor.text.get("sel.first", "sel.last") == "0xad23d"
    app.editor.set_text(TRES_ERRORES)
    app.analyze()
    app.errors_panel.tree.selection_set("0")
    app.root.update()
    assert app.editor.text.index("insert") == "2.15"


def test_zoom_limites(app) -> None:
    app.editor.set_text(VALIDO)
    app.analyze()
    for _ in range(40):
        app.canvas_panel.zoom_in()
    assert app.canvas_panel.scale == pytest.approx(3.0)
    for _ in range(40):
        app.canvas_panel.zoom_out()
    assert app.canvas_panel.scale == pytest.approx(0.3)


def test_tabla_ll1_sin_conflictos(app) -> None:
    assert app.grammar_panel.conflicts_label.cget("text") == "Gramática LL(1): sin conflictos"


def test_ejemplos_oficiales(app) -> None:
    app.editor.set_text(_ejemplo_o_skip("ok_1_completo.nr"))
    app.analyze()
    assert app.tree is not None and _filas(app.errors_panel.tree) == 0
    app.load_example("error_1_mixto.nr")
    assert _filas(app.errors_panel.tree) == 3


# --- format_trace (no necesita pantalla) ----------------------------------------


def test_format_trace_hexadecimal() -> None:
    token = Lexer("TARGET NODE 0xad23d").tokenize().tokens[2]
    texto = format_trace(token)
    assert "Token: HEX_ADDR" in texto
    assert "Lexema: 0xad23d" in texto
    assert "Posición: 1:13" in texto
    assert "Autómata: AFD enteros y hexadecimales (Tabla 2)" in texto
    assert "Traza: q0 —0→ q1 —x→ q3 —a→ q4 —d→ q4" in texto
    assert "Estado final: q4 ∈ F → HEX_ADDR" in texto


def test_format_trace_larga_se_recorta() -> None:
    token = Lexer('"' + "a" * 20 + '"').tokenize().tokens[0]
    linea = next(l for l in format_trace(token).splitlines() if l.startswith("Traza:"))
    assert linea.count("→") == 10  # 6 primeras + 4 últimas
    assert " … " in linea


# --- Regresiones encontradas en la auditoría -----------------------------------


def test_emoji_no_desplaza_resaltado_ni_errores(app) -> None:
    """Tk 8.6 cuenta un emoji como dos posiciones; el lexer, como una."""
    app.editor.set_text("TARGET NODE 0x1 { \U0001F600 CLEAR LOGS; }")
    app.analyze()
    texto = app.editor.text
    rangos = texto.tag_ranges("tk_cmd")
    assert texto.get(rangos[-2], rangos[-1]) == "LOGS"
    error = texto.tag_ranges("error")
    assert texto.get(error[0], error[1]) == "\U0001F600"
    app.editor.goto(1, 21, 5)  # CLEAR, columna del lexer
    assert texto.get("sel.first", "sel.last") == "CLEAR"
    assert app.cursor_label.cget("text") == "Ln 1, Col 21"


def test_arbol_grafico_se_dibuja_solo_al_mostrarse(app) -> None:
    """Dibujar el Canvas es lo más costoso: no se hace con la pestaña oculta."""
    app.editor.set_text(VALIDO)
    app.analyze()  # selecciona la pestaña Árbol de derivación
    panel = app.canvas_panel
    assert panel.layout is not None
    assert panel._pendiente and not panel.canvas.find_all()
    panel.zoom_in()  # cualquier acción que dibuje resuelve lo pendiente
    assert not panel._pendiente and panel.canvas.find_withtag("terminal")


def test_destruccion(_aplicacion) -> None:
    """Debe ser la última prueba que usa la ventana."""
    root = _aplicacion.root
    root.destroy()
    with pytest.raises(tk.TclError):
        root.winfo_exists()
