"""Ventana principal de NetRunner Analyzer."""

from __future__ import annotations

import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from netrunner.diagnostics import LEXICO, Diagnostic
from netrunner.examples import EXAMPLES, read_example
from netrunner.gui import theme
from netrunner.gui.editor import CodeEditor
from netrunner.gui.panels import (
    DerivationPanel,
    ErrorsPanel,
    GrammarPanel,
    SummaryBar,
    TokensPanel,
)
from netrunner.gui.tree_canvas import TreeCanvas
from netrunner.lexer import Lexer
from netrunner.parser import Parser
from netrunner.tokens import Token
from netrunner.tree import Node, simplify

TITLE = "NetRunner Analyzer — Analizador léxico y sintáctico"
SUBTITLE = ("DSL para simular secuencias de ciberataques, escaneo de red y "
            "evasión de sistemas de defensa")
COURSE = "Teoría de Lenguajes Formales · Universidad del Quindío · 2026-2"
AUTO_DELAY_MS = 600
LARGE_INPUT = 200 * 1024
STARTUP_EXAMPLE = "ok_1_completo.nr"


class NetRunnerApp:
    """Aplicación de escritorio: editor + paneles de resultados."""

    def __init__(self, root: tk.Tk, archivo: str | None = None) -> None:
        self.root = root
        self.fonts = theme.setup_theme(root)
        self.current_path: Path | None = None
        self.tree: Node | None = None
        self._simplified: Node | None = None
        self._after_id: str | None = None

        root.title(TITLE)
        root.minsize(1000, 650)
        self._centrar(1280, 800)

        self.simplify_var = tk.BooleanVar(value=False)
        self.simplify_var.trace_add("write", lambda *_: self._refresh_trees())
        self.auto_var = tk.BooleanVar(value=False)

        self._cabecera()
        self._barra_herramientas()
        self._barra_estado()  # antes del cuerpo para que nunca quede oculta
        self._cuerpo()
        self._atajos()
        self._ajustar_division()

        if archivo:
            self.open_path(Path(archivo))
        else:
            self.load_example(STARTUP_EXAMPLE)

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------

    def _centrar(self, ancho: int, alto: int) -> None:
        x = max(0, (self.root.winfo_screenwidth() - ancho) // 2)
        y = max(0, (self.root.winfo_screenheight() - alto) // 2)
        self.root.geometry(f"{ancho}x{alto}+{x}+{y}")

    def _ajustar_division(self, intentos: int = 40) -> None:
        """Deja el editor en ~45 % del ancho (espera a que la ventana tenga tamaño)."""
        ancho = self.paned.winfo_width()
        if ancho < 200:
            if intentos > 0:
                self.root.after(50, self._ajustar_division, intentos - 1)
            return
        self.paned.sashpos(0, int(ancho * 0.45))

    def _cabecera(self) -> None:
        cab = ttk.Frame(self.root, style="Header.TFrame", padding=(16, 8))
        cab.pack(fill="x")
        ttk.Label(cab, text="NET//RUNNER", style="Title.TLabel").grid(
            row=0, column=0, sticky="w")
        ttk.Label(cab, text=COURSE, style="Muted.TLabel").grid(
            row=0, column=1, sticky="e")
        ttk.Label(cab, text=SUBTITLE, style="Muted.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w")
        cab.columnconfigure(1, weight=1)
        tk.Frame(self.root, height=1, background=theme.NEON).pack(fill="x")

    def _barra_herramientas(self) -> None:
        barra = ttk.Frame(self.root, padding=(10, 8))
        barra.pack(fill="x")
        ttk.Button(barra, text="Abrir archivo", command=self.open_file).pack(side="left")
        ttk.Button(barra, text="Guardar", command=self.save_file).pack(side="left", padx=(6, 0))
        ttk.Button(barra, text="Analizar", style="Accent.TButton",
                   command=self.analyze).pack(side="left", padx=(6, 0))
        ttk.Button(barra, text="Limpiar", command=self.clear).pack(side="left", padx=(6, 0))

        ejemplos = ttk.Menubutton(barra, text="Ejemplos")
        menu = tk.Menu(ejemplos, tearoff=False)
        for nombre in EXAMPLES:
            menu.add_command(label=nombre, command=lambda n=nombre: self.load_example(n))
        ejemplos.configure(menu=menu)
        ejemplos.pack(side="left", padx=(6, 0))

        ttk.Checkbutton(barra, text="Analizar al escribir",
                        variable=self.auto_var).pack(side="left", padx=(18, 0))
        ttk.Label(barra, text="F5 / Ctrl+Enter: analizar", foreground=theme.MUTED).pack(
            side="right")

    def _cuerpo(self) -> None:
        self.paned = ttk.Panedwindow(self.root, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        self.editor = CodeEditor(self.paned, self.fonts, on_change=self._texto_cambiado,
                                 on_cursor=self._cursor)
        self.paned.add(self.editor, weight=45)

        derecha = ttk.Frame(self.paned)
        self.paned.add(derecha, weight=55)
        self.summary = SummaryBar(derecha, self.fonts)
        self.summary.pack(fill="x", padx=(6, 0))
        self.notebook = ttk.Notebook(derecha)
        self.notebook.pack(fill="both", expand=True, padx=(6, 0), pady=(6, 0))

        self.tokens_panel = TokensPanel(self.notebook, self.fonts,
                                        on_select=self._resaltar_token,
                                        on_status=self.set_status)
        self.derivation = DerivationPanel(self.notebook, self.fonts, self.simplify_var,
                                          on_select=self._resaltar_token,
                                          on_status=self.set_status)
        self.canvas_panel = TreeCanvas(self.notebook, self.fonts, self.simplify_var,
                                       on_select=self._resaltar_token,
                                       on_status=self.set_status)
        self.errors_panel = ErrorsPanel(self.notebook, self.fonts, on_goto=self._ir_a_error)
        self.grammar_panel = GrammarPanel(self.notebook, self.fonts)
        for panel, titulo in ((self.tokens_panel, "Tokens"),
                              (self.derivation, "Árbol de derivación"),
                              (self.canvas_panel, "Árbol gráfico"),
                              (self.errors_panel, "Errores"),
                              (self.grammar_panel, "Gramática")):
            self.notebook.add(panel, text=titulo)

    def _barra_estado(self) -> None:
        barra = ttk.Frame(self.root, style="Panel.TFrame")
        barra.pack(fill="x", side="bottom")
        tk.Frame(self.root, height=1, background=theme.BORDER).pack(fill="x", side="bottom")
        self.status = ttk.Label(barra, text="Listo.", style="Status.TLabel")
        self.status.pack(side="left")
        self.cursor_label = ttk.Label(barra, text="Ln 1, Col 1", style="Status.TLabel")
        self.cursor_label.pack(side="right")

    def _atajos(self) -> None:
        acciones = {
            "<Control-o>": self.open_file, "<Control-O>": self.open_file,
            "<Control-s>": self.save_file, "<Control-S>": self.save_file,
            "<F5>": self.analyze, "<Control-Return>": self.analyze,
        }
        for secuencia, accion in acciones.items():
            def manejador(_e: tk.Event, a=accion) -> str:
                a()
                return "break"
            # En el Text se enlaza a la instancia para anular sus atajos de clase
            # (Ctrl+O inserta línea, Ctrl+Enter inserta salto).
            self.editor.text.bind(secuencia, manejador)
            self.root.bind(secuencia, manejador)

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    def set_status(self, mensaje: str) -> None:
        self.status.configure(text=mensaje)

    def _cursor(self, linea: int, col: int) -> None:
        self.cursor_label.configure(text=f"Ln {linea}, Col {col}")

    def _resaltar_token(self, token: Token) -> None:
        if token.length:
            self.editor.select_range(token.line, token.col, token.length)

    def _ir_a_error(self, d: Diagnostic) -> None:
        self.editor.goto(d.line, d.col, d.length)

    def _texto_cambiado(self) -> None:
        if not self.auto_var.get():
            return
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
        self._after_id = self.root.after(AUTO_DELAY_MS, self._analisis_automatico)

    def _analisis_automatico(self) -> None:
        self._after_id = None
        self.analyze()

    # ------------------------------------------------------------------
    # Archivos y ejemplos
    # ------------------------------------------------------------------

    def open_file(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Abrir archivo NetRunner",
            filetypes=[("NetRunner", "*.nr"), ("Texto", "*.txt"),
                       ("Todos los archivos", "*.*")])
        if ruta:
            self.open_path(Path(ruta))

    def open_path(self, ruta: Path) -> None:
        try:
            contenido = ruta.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            messagebox.showerror("Abrir archivo", f"No se pudo abrir '{ruta}':\n{e}")
            return
        self.current_path = ruta
        self.editor.set_text(contenido)
        self.analyze()
        self.set_status(f"Archivo abierto: {ruta.name}. {self.status.cget('text')}")

    def save_file(self) -> None:
        ruta = self.current_path
        if ruta is None:
            elegido = filedialog.asksaveasfilename(
                title="Guardar archivo", defaultextension=".nr",
                filetypes=[("NetRunner", "*.nr"), ("Texto", "*.txt"),
                           ("Todos los archivos", "*.*")])
            if not elegido:
                return
            ruta = Path(elegido)
        try:
            ruta.write_text(self.editor.get_text(), encoding="utf-8")
        except OSError as e:
            messagebox.showerror("Guardar", f"No se pudo guardar '{ruta}':\n{e}")
            return
        self.current_path = ruta
        self.set_status(f"Guardado en {ruta}")

    def load_example(self, nombre: str) -> None:
        """Carga un ejemplo y lo analiza (Guardar pedirá una ruta nueva)."""
        try:
            contenido = read_example(nombre)
        except (OSError, ValueError) as e:
            messagebox.showerror("Ejemplos", f"No se pudo cargar '{nombre}':\n{e}")
            return
        self.current_path = None
        self.editor.set_text(contenido)
        self.analyze()
        self.set_status(f"Ejemplo cargado: {nombre}. {self.status.cget('text')}")

    def clear(self) -> None:
        self.current_path = None
        self.editor.set_text("")
        self.analyze()
        self.set_status("Editor limpio.")

    # ------------------------------------------------------------------
    # Análisis
    # ------------------------------------------------------------------

    def _current_tree(self) -> Node | None:
        if self.tree is None or not self.simplify_var.get():
            return self.tree
        if self._simplified is None:
            self._simplified = simplify(self.tree)
        return self._simplified

    def _refresh_trees(self, hay_codigo: bool = True) -> None:
        arbol = self._current_tree()
        self.derivation.set_tree(arbol, hay_codigo)
        self.canvas_panel.set_tree(arbol, hay_codigo)

    def _limpiar_paneles(self) -> None:
        self.tree = self._simplified = None
        self.summary.show_empty()
        self.tokens_panel.set_tokens([], [])
        self._refresh_trees(hay_codigo=False)
        self.errors_panel.set_errors([], hay_codigo=False)
        self.editor.clear_marks()

    def analyze(self) -> None:
        """Ejecuta el análisis léxico y sintáctico y actualiza toda la interfaz."""
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        try:
            texto = self.editor.get_text()
            if not texto.strip():
                self._limpiar_paneles()
                self.set_status("Sin código para analizar.")
                return
            if len(texto.encode("utf-8")) > LARGE_INPUT:
                self.set_status("Analizando…")
                self.root.update_idletasks()

            lex = Lexer(texto).tokenize()
            resultado = Parser(lex.tokens).parse()
            errores = sorted(lex.errors + resultado.errors, key=lambda d: (d.line, d.col))
            n_lex = sum(1 for d in errores if d.kind == LEXICO)
            n_sin = len(errores) - n_lex

            self.tree, self._simplified = resultado.tree, None
            nodos = self.tree.count() if self.tree is not None else None
            n_tokens = len(lex.tokens) - 1  # sin EOF

            self.summary.show(n_tokens, n_lex, n_sin, nodos)
            self.tokens_panel.set_tokens(lex.tokens, lex.all_tokens)
            self._refresh_trees()
            self.errors_panel.set_errors(errores)
            self.editor.highlight_tokens(lex.all_tokens)
            self.editor.mark_errors(errores)

            if errores:
                self.notebook.select(self.errors_panel)
                self.set_status(f"Análisis con errores: {n_lex} léxicos, {n_sin} sintácticos.")
            else:
                self.notebook.select(self.derivation)
                self.set_status(f"Análisis correcto: {n_tokens} tokens, "
                                f"árbol de {nodos} nodos.")
        except Exception as e:  # la interfaz nunca debe cerrarse por un fallo
            traceback.print_exc()
            messagebox.showerror("Error inesperado",
                                 f"Ocurrió un error inesperado durante el análisis:\n{e}")
            self.set_status("Error inesperado durante el análisis.")


def run(archivo: str | None = None) -> None:
    """Crea la ventana principal y entra en el ciclo de eventos."""
    root = tk.Tk()
    NetRunnerApp(root, archivo)
    root.mainloop()
