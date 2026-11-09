"""Paneles de resultados: resumen, tokens, árbol, errores y gramática."""

from __future__ import annotations

import csv
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, ttk

from netrunner.diagnostics import LEXICO, Diagnostic
from netrunner.grammar import (
    END,
    LL1_GRAMMAR,
    build_ll1_table,
    find_conflicts,
    format_first_follow,
    format_ll1_grammar,
    format_original_grammar,
    format_production,
    nonterminals,
    production_label,
    terminals,
)
from netrunner.gui import theme
from netrunner.tokens import Token
from netrunner.tree import Node, to_ascii, to_dot

NO_TREE_MESSAGE = ("El código tiene errores. Corrígelos para generar el árbol de "
                   "derivación (ver pestaña Errores).")

TokenCallback = Callable[[Token], None]
StatusCallback = Callable[[str], None]

_VISIBLES = {" ": "␠", "\n": "↵", "\t": "⇥", "\r": "␍"}


def _visible(c: str) -> str:
    return _VISIBLES.get(c, c)


def format_trace(token: Token) -> str:
    """Texto de la sección "Traza del AFD" para un token.

    Con más de 12 transiciones se muestran las 6 primeras y las 4 últimas.
    """
    lineas = [
        f"Token: {token.type.name}",
        f"Lexema: {''.join(_visible(c) for c in token.lexeme) or '(vacío)'}",
        f"Posición: {token.line}:{token.col}",
        "",
        f"Autómata: {token.family}",
        "",
    ]
    trace = token.trace
    if not trace:
        lineas.append("Traza: (sin transiciones: fin de la entrada)")
        return "\n".join(lineas)

    def tramo(transiciones: tuple[tuple[str, str, str], ...]) -> str:
        partes = [transiciones[0][0]]
        for _, c, destino in transiciones:
            partes.append(f"—{_visible(c)}→ {destino}")
        return " ".join(partes)

    if len(trace) > 12:
        texto = f"{tramo(trace[:6])} … {tramo(trace[-4:])}"
    else:
        texto = tramo(trace)
    lineas.append(f"Traza: {texto}")
    lineas.append("")
    lineas.append(f"Estado final: {token.accept_state} ∈ F → {token.type.name}")
    return "\n".join(lineas)


def _scrolled_tree(parent: tk.Misc, **kw: object) -> tuple[ttk.Frame, ttk.Treeview]:
    """Treeview con barras de desplazamiento vertical y horizontal."""
    marco = ttk.Frame(parent)
    arbol = ttk.Treeview(marco, **kw)
    by = ttk.Scrollbar(marco, orient="vertical", command=arbol.yview)
    bx = ttk.Scrollbar(marco, orient="horizontal", command=arbol.xview)
    arbol.configure(yscrollcommand=by.set, xscrollcommand=bx.set)
    arbol.grid(row=0, column=0, sticky="nsew")
    by.grid(row=0, column=1, sticky="ns")
    bx.grid(row=1, column=0, sticky="ew")
    marco.rowconfigure(0, weight=1)
    marco.columnconfigure(0, weight=1)
    return marco, arbol


# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------


class SummaryBar(ttk.Frame):
    """Franja con contadores y veredicto del último análisis."""

    def __init__(self, parent: tk.Misc, fonts: theme.Fonts) -> None:
        super().__init__(parent, style="Panel.TFrame", padding=(10, 6))
        self.tokens = ttk.Label(self, style="Panel.TLabel")
        self.lexicos = ttk.Label(self, style="Panel.TLabel")
        self.sintacticos = ttk.Label(self, style="Panel.TLabel")
        self.nodos = ttk.Label(self, style="Panel.TLabel")
        self.verdict = tk.Label(self, background=theme.PANEL, font=fonts.mono_bold)
        # Dos filas para que quepa en el panel derecho:
        #   VEREDICTO        Tokens: N         Nodos del árbol: N
        #                    Errores léxicos   Errores sintácticos
        self.verdict.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 24))
        self.tokens.grid(row=0, column=1, sticky="w", padx=(0, 16))
        self.nodos.grid(row=0, column=2, sticky="w")
        self.lexicos.grid(row=1, column=1, sticky="w", padx=(0, 16))
        self.sintacticos.grid(row=1, column=2, sticky="w")
        self.show_empty()

    def show(self, tokens: int, lexicos: int, sintacticos: int, nodos: int | None) -> None:
        self.tokens.configure(text=f"Tokens: {tokens}")
        self.lexicos.configure(text=f"Errores léxicos: {lexicos}")
        self.sintacticos.configure(text=f"Errores sintácticos: {sintacticos}")
        self.nodos.configure(text=f"Nodos del árbol: {nodos if nodos is not None else '—'}")
        if lexicos or sintacticos:
            self.verdict.configure(text="CÓDIGO CON ERRORES", foreground=theme.RED)
        else:
            self.verdict.configure(text="CÓDIGO VÁLIDO", foreground=theme.NEON)

    def show_empty(self) -> None:
        self.show(0, 0, 0, None)
        self.verdict.configure(text="SIN CÓDIGO", foreground=theme.MUTED)


# ---------------------------------------------------------------------------
# Pestaña 1: Tokens
# ---------------------------------------------------------------------------


class TokensPanel(ttk.Frame):
    """Tabla de tokens con traza del AFD del token seleccionado."""

    def __init__(self, parent: tk.Misc, fonts: theme.Fonts,
                 on_select: TokenCallback, on_status: StatusCallback) -> None:
        super().__init__(parent, padding=6)
        self.on_select = on_select
        self.on_status = on_status
        self._tokens: list[Token] = []
        self._all_tokens: list[Token] = []
        self._visibles: list[Token] = []

        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(0, 6))
        self.show_aux = tk.BooleanVar(value=False)
        ttk.Checkbutton(barra, text="Mostrar espacios y comentarios",
                        variable=self.show_aux, command=self._llenar).pack(side="left")
        ttk.Button(barra, text="Exportar CSV", style="Tool.TButton", command=self.export_csv).pack(side="right")

        # La traza se empaqueta primero (abajo) para que siempre tenga espacio.
        self.trace = theme.readonly_text(self, fonts, height=9)
        self.trace.pack(side="bottom", fill="x")
        ttk.Label(self, text="Traza del AFD", style="Section.TLabel").pack(
            side="bottom", anchor="w", pady=(8, 2))

        columnas = ("n", "linea", "col", "tipo", "lexema")
        marco, self.tree = _scrolled_tree(self, columns=columnas, show="headings",
                                          selectmode="browse")
        for col, titulo, ancho, ancla in (
            ("n", "#", 50, "e"), ("linea", "Línea", 50, "e"), ("col", "Col", 50, "e"),
            ("tipo", "Tipo", fonts.mono.measure("COMENTARIO") + 20, "w"),
            ("lexema", "Lexema", 220, "w"),
        ):
            self.tree.heading(col, text=titulo, anchor=ancla)
            self.tree.column(col, width=theme.column_width(fonts, titulo, ancho),
                             anchor=ancla, stretch=(col == "lexema"))
        self.tree.tag_configure("par", background=theme.PANEL)
        self.tree.tag_configure("impar", background=theme.PANEL_2)
        self.tree.tag_configure("aux", foreground=theme.MUTED)
        self.tree.bind("<<TreeviewSelect>>", self._seleccion)
        marco.pack(fill="both", expand=True)

    def set_tokens(self, tokens: list[Token], all_tokens: list[Token]) -> None:
        self._tokens, self._all_tokens = tokens, all_tokens
        self._llenar()

    def _llenar(self) -> None:
        self.tree.delete(*self.tree.get_children())
        theme.set_readonly_text(self.trace, "Selecciona un token para ver su recorrido "
                                            "por el autómata.")
        self._visibles = self._all_tokens if self.show_aux.get() else self._tokens
        for i, t in enumerate(self._visibles):
            lexema = "".join(_visible(c) for c in t.lexeme) if t.lexeme else "(fin)"
            tags = ["par" if i % 2 == 0 else "impar"]
            if t.type.name in ("ESPACIO", "COMENTARIO", "EOF"):
                tags.append("aux")
            self.tree.insert("", "end", iid=str(i), tags=tags,
                             values=(i + 1, t.line, t.col, t.type.name, lexema))

    def _seleccion(self, _evento: tk.Event) -> None:
        seleccion = self.tree.selection()
        if not seleccion:
            return
        token = self._visibles[int(seleccion[0])]
        theme.set_readonly_text(self.trace, format_trace(token))
        self.on_select(token)

    def export_csv(self) -> None:
        if not self._visibles:
            self.on_status("No hay tokens para exportar.")
            return
        ruta = filedialog.asksaveasfilename(
            title="Exportar tokens", defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos los archivos", "*.*")])
        if not ruta:
            return
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            escritor = csv.writer(f)
            escritor.writerow(["#", "Línea", "Col", "Tipo", "Lexema", "Autómata"])
            for i, t in enumerate(self._visibles, start=1):
                escritor.writerow([i, t.line, t.col, t.type.name, t.lexeme, t.family])
        self.on_status(f"Tokens exportados a {ruta}")


# ---------------------------------------------------------------------------
# Pestaña 2: Árbol de derivación
# ---------------------------------------------------------------------------


class DerivationPanel(ttk.Frame):
    """Árbol de derivación en un Treeview."""

    def __init__(self, parent: tk.Misc, fonts: theme.Fonts, simplify_var: tk.BooleanVar,
                 on_select: TokenCallback, on_status: StatusCallback) -> None:
        super().__init__(parent, padding=6)
        self.on_select = on_select
        self.on_status = on_status
        self.root_node: Node | None = None
        self._nodos: dict[str, Node] = {}

        # Dos filas de controles para que quepan en el panel derecho.
        fila1, fila2 = ttk.Frame(self), ttk.Frame(self)
        fila1.pack(fill="x", pady=(0, 4))
        fila2.pack(fill="x", pady=(0, 6))
        ttk.Checkbutton(fila1, text="Simplificar", variable=simplify_var).pack(side="left")
        for barra, texto, comando in ((fila1, "Expandir todo", self.expand_all),
                                      (fila1, "Colapsar todo", self.collapse_all),
                                      (fila2, "Copiar como texto", self.copy_text),
                                      (fila2, "Exportar .txt", self.export_txt),
                                      (fila2, "Exportar .dot", self.export_dot)):
            ttk.Button(barra, text=texto, style="Tool.TButton", command=comando).pack(
                side="left", padx=(0 if texto == "Copiar como texto" else 4, 0))

        self.message = ttk.Label(self, text=NO_TREE_MESSAGE, style="Bad.TLabel",
                                 wraplength=600)
        marco, self.tree = _scrolled_tree(self, columns=("token", "pos"),
                                          selectmode="browse")
        self.tree.heading("#0", text="Árbol", anchor="w")
        self.tree.heading("token", text="Token", anchor="w")
        self.tree.heading("pos", text="Posición", anchor="w")
        self.tree.column("#0", width=360, stretch=True)
        self.tree.column("token", width=fonts.mono.measure("HEX_ADDR") + 24, stretch=False)
        self.tree.column("pos", width=theme.column_width(fonts, "Posición", 80),
                         stretch=False)
        self.tree.tag_configure("nt", foreground=theme.CYAN)
        self.tree.tag_configure("t", foreground=theme.NEON)
        self.tree.tag_configure("eps", foreground=theme.MUTED)
        self.tree.bind("<<TreeviewSelect>>", self._seleccion)
        self._marco = marco
        marco.pack(fill="both", expand=True)

    def set_tree(self, raiz: Node | None, hay_codigo: bool = True) -> None:
        """Muestra el árbol, o el aviso si no existe."""
        self.root_node = raiz
        self.tree.delete(*self.tree.get_children())
        self._nodos.clear()
        if raiz is None:
            self.message.configure(text=NO_TREE_MESSAGE if hay_codigo else "")
            self.message.pack(before=self._marco, anchor="w", pady=(0, 6))
            return
        self.message.pack_forget()
        pila: list[tuple[Node, str, int]] = [(raiz, "", 0)]
        while pila:
            nodo, padre, prof = pila.pop()
            if nodo.is_terminal:
                assert nodo.token is not None
                tag, valores = "t", (nodo.symbol, f"{nodo.token.line}:{nodo.token.col}")
            elif nodo.is_epsilon:
                tag, valores = "eps", ("", "")
            else:
                tag, valores = "nt", ("", "")
            iid = self.tree.insert(padre, "end", text=nodo.label, values=valores,
                                   tags=(tag,), open=prof < 3)
            self._nodos[iid] = nodo
            # Se apilan al revés para sacarlos (e insertarlos) de izquierda a derecha.
            for hijo in reversed(nodo.children):
                pila.append((hijo, iid, prof + 1))

    def _seleccion(self, _evento: tk.Event) -> None:
        seleccion = self.tree.selection()
        if seleccion:
            nodo = self._nodos.get(seleccion[0])
            if nodo is not None and nodo.token is not None:
                self.on_select(nodo.token)

    def _todos(self) -> list[str]:
        items, pila = [], list(self.tree.get_children(""))
        while pila:
            item = pila.pop()
            items.append(item)
            pila.extend(self.tree.get_children(item))
        return items

    def expand_all(self) -> None:
        for item in self._todos():
            self.tree.item(item, open=True)

    def collapse_all(self) -> None:
        for item in self._todos():
            self.tree.item(item, open=False)

    def copy_text(self) -> None:
        if self.root_node is None:
            self.on_status("No hay árbol para copiar.")
            return
        self.clipboard_clear()
        self.clipboard_append(to_ascii(self.root_node))
        self.on_status("Árbol copiado al portapapeles.")

    def _exportar(self, extension: str, descripcion: str, contenido: Callable[[Node], str]) -> None:
        if self.root_node is None:
            self.on_status("No hay árbol para exportar.")
            return
        ruta = filedialog.asksaveasfilename(
            title="Exportar árbol", defaultextension=extension,
            filetypes=[(descripcion, f"*{extension}"), ("Todos los archivos", "*.*")])
        if ruta:
            Path(ruta).write_text(contenido(self.root_node) + "\n", encoding="utf-8")
            self.on_status(f"Árbol exportado a {ruta}")

    def export_txt(self) -> None:
        self._exportar(".txt", "Texto", to_ascii)

    def export_dot(self) -> None:
        self._exportar(".dot", "Graphviz DOT", to_dot)


# ---------------------------------------------------------------------------
# Pestaña 4: Errores
# ---------------------------------------------------------------------------


class ErrorsPanel(ttk.Frame):
    """Lista de diagnósticos léxicos y sintácticos."""

    def __init__(self, parent: tk.Misc, fonts: theme.Fonts,
                 on_goto: Callable[[Diagnostic], None]) -> None:
        super().__init__(parent, padding=6)
        self.on_goto = on_goto
        self._diagnosticos: list[Diagnostic] = []
        self.message = ttk.Label(self, text="", style="Ok.TLabel")
        self.message.pack(anchor="w", pady=(0, 6))
        columnas = ("n", "tipo", "linea", "col", "mensaje")
        marco, self.tree = _scrolled_tree(self, columns=columnas, show="headings",
                                          selectmode="browse")
        for col, titulo, ancho, ancla in (
            ("n", "#", 40, "e"),
            ("tipo", "Tipo", fonts.mono.measure("Sintáctico") + 20, "w"),
            ("linea", "Línea", 50, "e"), ("col", "Columna", 50, "e"),
            ("mensaje", "Mensaje", 900, "w"),
        ):
            self.tree.heading(col, text=titulo, anchor=ancla)
            self.tree.column(col, width=theme.column_width(fonts, titulo, ancho),
                             anchor=ancla, stretch=(col == "mensaje"))
        self.tree.tag_configure("lexico", foreground=theme.RED)
        self.tree.tag_configure("sintactico", foreground=theme.AMBER)
        self.tree.bind("<<TreeviewSelect>>", self._ir)
        self.tree.bind("<Double-1>", self._ir)
        marco.pack(fill="both", expand=True)

    def set_errors(self, diagnosticos: list[Diagnostic], hay_codigo: bool = True) -> None:
        self._diagnosticos = sorted(diagnosticos, key=lambda d: (d.line, d.col))
        self.tree.delete(*self.tree.get_children())
        for i, d in enumerate(self._diagnosticos):
            lexico = d.kind == LEXICO
            self.tree.insert("", "end", iid=str(i),
                             tags=("lexico" if lexico else "sintactico",),
                             values=(i + 1, "Léxico" if lexico else "Sintáctico",
                                     d.line, d.col, d.message))
        if self._diagnosticos:
            self.message.configure(text=f"{len(self._diagnosticos)} error(es) encontrados.",
                                   style="Bad.TLabel")
        elif hay_codigo:
            self.message.configure(text="Sin errores léxicos ni sintácticos.",
                                   style="Ok.TLabel")
        else:
            self.message.configure(text="")

    def _ir(self, _evento: tk.Event) -> None:
        seleccion = self.tree.selection()
        if seleccion:
            self.on_goto(self._diagnosticos[int(seleccion[0])])


# ---------------------------------------------------------------------------
# Pestaña 5: Gramática
# ---------------------------------------------------------------------------


class GrammarPanel(ttk.Frame):
    """Gramáticas, FIRST/FOLLOW y tabla LL(1) calculados por grammar.py."""

    def __init__(self, parent: tk.Misc, fonts: theme.Fonts) -> None:
        super().__init__(parent, padding=6)
        interno = ttk.Notebook(self)
        interno.pack(fill="both", expand=True)

        for titulo, contenido in (
            ("Gramática original", format_original_grammar()
             + "\n\n(con recursividad izquierda)"),
            ("Gramática LL(1)", format_ll1_grammar()
             + "\n\n(sin recursividad izquierda y factorizada)"),
            ("FIRST y FOLLOW", format_first_follow(LL1_GRAMMAR)),
        ):
            marco = ttk.Frame(interno)
            texto = theme.readonly_text(marco, fonts)
            by = ttk.Scrollbar(marco, orient="vertical", command=texto.yview)
            bx = ttk.Scrollbar(marco, orient="horizontal", command=texto.xview)
            texto.configure(yscrollcommand=by.set, xscrollcommand=bx.set)
            texto.grid(row=0, column=0, sticky="nsew")
            by.grid(row=0, column=1, sticky="ns")
            bx.grid(row=1, column=0, sticky="ew")
            marco.rowconfigure(0, weight=1)
            marco.columnconfigure(0, weight=1)
            theme.set_readonly_text(texto, contenido)
            interno.add(marco, text=titulo)

        interno.add(self._tabla_ll1(interno, fonts), text="Tabla LL(1)")

    def _tabla_ll1(self, parent: tk.Misc, fonts: theme.Fonts) -> ttk.Frame:
        marco = ttk.Frame(parent)
        tabla = build_ll1_table(LL1_GRAMMAR)
        conflictos = find_conflicts(tabla)
        columnas_t = terminals(LL1_GRAMMAR) + [END]
        columnas = ["nt"] + [f"t{i}" for i in range(len(columnas_t))]

        sub, arbol = _scrolled_tree(marco, columns=columnas, show="headings",
                                    selectmode="browse")
        arbol.heading("nt", text="No terminal", anchor="w")
        arbol.column("nt", width=fonts.mono.measure("<condicional'>") + 20,
                     stretch=False, anchor="w")
        for col, terminal in zip(columnas[1:], columnas_t):
            arbol.heading(col, text=terminal)
            arbol.column(col, width=max(fonts.mono.measure(terminal) + 24, 52),
                         stretch=False, anchor="center")
        arbol.tag_configure("par", background=theme.PANEL)
        arbol.tag_configure("impar", background=theme.PANEL_2)

        self.detalle = ttk.Label(marco, text="Selecciona una fila para ver sus producciones.",
                                 style="TLabel", wraplength=900, justify="left")
        for i, nt in enumerate(nonterminals(LL1_GRAMMAR)):
            valores = [nt]
            for terminal in columnas_t:
                indice = tabla.get((nt, terminal))
                valores.append("" if indice is None else production_label(LL1_GRAMMAR, indice))
            arbol.insert("", "end", iid=nt, values=valores,
                         tags=("par" if i % 2 == 0 else "impar",))

        def mostrar_producciones(_evento: tk.Event) -> None:
            seleccion = arbol.selection()
            if not seleccion:
                return
            nt = seleccion[0]
            lineas = [format_production(LL1_GRAMMAR, i)
                      for i, (izq, _) in enumerate(LL1_GRAMMAR) if izq == nt]
            self.detalle.configure(text="\n".join(lineas))

        arbol.bind("<<TreeviewSelect>>", mostrar_producciones)
        sub.pack(fill="both", expand=True)
        self.detalle.pack(anchor="w", pady=(6, 0))

        if conflictos:
            texto = "Gramática LL(1): conflictos en " + ", ".join(
                f"M[{nt}, {t}] = {', '.join(production_label(LL1_GRAMMAR, i) for i in idx)}"
                for (nt, t), idx in conflictos.items())
            estilo = "Bad.TLabel"
        else:
            texto, estilo = "Gramática LL(1): sin conflictos", "Ok.TLabel"
        self.conflicts_label = ttk.Label(marco, text=texto, style=estilo)
        self.conflicts_label.pack(anchor="w", pady=(6, 0))
        return marco

