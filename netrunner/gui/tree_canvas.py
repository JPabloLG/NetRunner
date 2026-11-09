"""Dibujo del árbol sintáctico en un tk.Canvas con zoom y desplazamiento."""

from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, ttk

from netrunner.gui import theme
from netrunner.gui.panels import NO_TREE_MESSAGE
from netrunner.tokens import Token
from netrunner.tree import Node, to_svg
from netrunner.tree_layout import Layout, layout_tree

MIN_SCALE = 0.3
MAX_SCALE = 3.0
ZOOM_STEP = 1.15
BASE_FONT_SIZE = 10
BOX_H = 42  # dos líneas en los terminales: lexema y tipo
MARGIN = 24


class TreeCanvas(ttk.Frame):
    """Árbol gráfico: zoom, ajuste, pan con arrastre y clic en terminales."""

    def __init__(self, parent: tk.Misc, fonts: theme.Fonts, simplify_var: tk.BooleanVar,
                 on_select: Callable[[Token], None],
                 on_status: Callable[[str], None]) -> None:
        super().__init__(parent, padding=6)
        self.fonts = fonts
        self.on_select = on_select
        self.on_status = on_status
        self.root_node: Node | None = None
        self.layout: Layout | None = None
        self.scale = 1.0
        self._mensaje = ""
        self._press: tuple[int, int] | None = None
        self._arrastrado = False
        self._base_font = tkfont.Font(self, family=fonts.family, size=BASE_FONT_SIZE)
        self._pendiente = False
        self.bind("<Map>", self._dibujar_pendiente)

        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(0, 6))
        for texto, comando in (("Zoom +", self.zoom_in), ("Zoom -", self.zoom_out),
                               ("Ajustar", self.fit), ("Exportar SVG", self.export_svg)):
            ttk.Button(barra, text=texto, style="Tool.TButton", command=comando).pack(
                side="left", padx=(0, 4))
        ttk.Checkbutton(barra, text="Simplificar", variable=simplify_var).pack(
            side="left", padx=(6, 0))
        self.zoom_label = ttk.Label(barra, text="100 %", foreground=theme.MUTED)
        self.zoom_label.pack(side="left", padx=(10, 0))

        marco = ttk.Frame(self)
        marco.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(marco, background=theme.BG, highlightthickness=0,
                                borderwidth=0)
        by = ttk.Scrollbar(marco, orient="vertical", command=self.canvas.yview)
        bx = ttk.Scrollbar(marco, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=by.set, xscrollcommand=bx.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        by.grid(row=0, column=1, sticky="ns")
        bx.grid(row=1, column=0, sticky="ew")
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)
        self._enlazar_eventos()

    # ------------------------------------------------------------------
    # Eventos (Windows, macOS y Linux)
    # ------------------------------------------------------------------

    def _enlazar_eventos(self) -> None:
        c = self.canvas
        c.bind("<MouseWheel>", lambda e: self._rueda(e, "y"))
        c.bind("<Shift-MouseWheel>", lambda e: self._rueda(e, "x"))
        c.bind("<Control-MouseWheel>", lambda e: self._rueda(e, "zoom"))
        if sys.platform.startswith("linux"):
            for boton, signo in (("4", 1), ("5", -1)):
                c.bind(f"<Button-{boton}>", lambda e, s=signo: self._rueda(e, "y", s))
                c.bind(f"<Shift-Button-{boton}>", lambda e, s=signo: self._rueda(e, "x", s))
                c.bind(f"<Control-Button-{boton}>",
                       lambda e, s=signo: self._rueda(e, "zoom", s))
        c.bind("<ButtonPress-1>", self._presionar)
        c.bind("<B1-Motion>", self._arrastrar)
        c.bind("<ButtonRelease-1>", self._soltar)
        c.bind("<Configure>", lambda _e: self._centrar_mensaje())

    def _rueda(self, evento: tk.Event, modo: str, signo: int | None = None) -> str:
        if signo is None:
            signo = 1 if evento.delta > 0 else -1
        if modo == "zoom":
            self._zoom(ZOOM_STEP if signo > 0 else 1 / ZOOM_STEP)
        elif modo == "x":
            self.canvas.xview_scroll(-signo * 3, "units")
        else:
            self.canvas.yview_scroll(-signo * 3, "units")
        return "break"

    def _presionar(self, evento: tk.Event) -> None:
        self._press = (evento.x, evento.y)
        self._arrastrado = False
        self.canvas.scan_mark(evento.x, evento.y)

    def _arrastrar(self, evento: tk.Event) -> None:
        if self._press is None:
            return
        dx, dy = evento.x - self._press[0], evento.y - self._press[1]
        if abs(dx) + abs(dy) > 3:
            self._arrastrado = True
        self.canvas.scan_dragto(evento.x, evento.y, gain=1)

    def _soltar(self, _evento: tk.Event) -> None:
        if not self._arrastrado:
            self._clic_en_nodo()
        self._press = None

    def _clic_en_nodo(self) -> None:
        if self.layout is None:
            return
        for item in self.canvas.find_withtag("current"):
            for tag in self.canvas.gettags(item):
                if tag.startswith("n") and tag[1:].isdigit():
                    nodo = self.layout.nodes[int(tag[1:])].node
                    if nodo.token is not None:
                        self.on_select(nodo.token)
                    return

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------

    def set_tree(self, raiz: Node | None, hay_codigo: bool = True) -> None:
        """Muestra un árbol nuevo (o el aviso si no hay árbol)."""
        self.root_node = raiz
        self.layout = None
        if raiz is None:
            self._mensaje = NO_TREE_MESSAGE if hay_codigo else ""
            self.canvas.delete("all")
            self.canvas.configure(scrollregion=(0, 0, 0, 0))
            self._centrar_mensaje()
            return
        self._mensaje = ""
        # El ancho de un terminal depende del lexema y del tipo (dos líneas);
        # el lexema determina el tipo, así que se mide por etiqueta. Cada texto
        # distinto se mide una sola vez: font.measure es una llamada a Tcl y un
        # árbol grande repite muchas veces las mismas etiquetas.
        medidas: dict[str, float] = {}

        def medir(texto: str) -> float:
            if texto not in medidas:
                medidas[texto] = self._base_font.measure(texto)
            return medidas[texto]

        anchos: dict[str, float] = {}
        pila = [raiz]
        while pila:
            nodo = pila.pop()
            pila.extend(nodo.children)
            ancho = medir(nodo.label)
            if nodo.is_terminal:
                ancho = max(ancho, medir(nodo.symbol))
            anchos[nodo.label] = max(anchos.get(nodo.label, 0), ancho)
        self.layout = layout_tree(raiz, lambda s: anchos[s], box_h=BOX_H)
        # Dibujar miles de figuras es lo más costoso: si la pestaña no está
        # visible, se pospone hasta que se muestre (evento <Map>).
        self._pendiente = True
        if self.winfo_ismapped():
            self._dibujar_pendiente()

    def _dibujar_pendiente(self, _evento: tk.Event | None = None) -> None:
        if self._pendiente and self.layout is not None:
            self.update_idletasks()
            self._dibujar()
            self._mostrar_raiz()

    def _mostrar_raiz(self) -> None:
        """Desplaza la vista para que la raíz quede centrada arriba."""
        if self.layout is None:
            return
        total = (self.layout.width + 2 * MARGIN) * self.scale
        raiz_x = (self.layout.nodes[0].x_centro + MARGIN) * self.scale
        visible = max(self.canvas.winfo_width(), 1)
        self.canvas.xview_moveto(max(0.0, (raiz_x - visible / 2) / total))
        self.canvas.yview_moveto(0)

    def _centrar_mensaje(self) -> None:
        if self.root_node is not None:
            return
        self.canvas.delete("mensaje")
        if self._mensaje:
            ancho = max(self.canvas.winfo_width(), 200)
            self.canvas.create_text(ancho / 2, 60, text=self._mensaje, fill=theme.RED,
                                    font=self.fonts.ui_bold, width=ancho - 40,
                                    justify="center", tags="mensaje")

    def _dibujar(self) -> None:
        self._pendiente = False
        c = self.canvas
        c.delete("all")
        if self.layout is None:
            return
        s = self.scale
        fuente = tkfont.Font(self, family=self.fonts.family,
                             size=max(5, round(BASE_FONT_SIZE * s)))
        fuente_tipo = tkfont.Font(self, family=self.fonts.family,
                                  size=max(4, round((BASE_FONT_SIZE - 2) * s)))
        self._fuentes = (fuente, fuente_tipo)  # evitar que el recolector las libere

        def px(v: float) -> float:
            return (v + MARGIN) * s

        # A escalas pequeñas el texto no cabe en las cajas: se omite.
        con_texto = s >= 0.45
        con_tipo = s >= 0.7
        nodos = self.layout.nodes
        for p in nodos:
            if p.indice_padre >= 0:
                padre = nodos[p.indice_padre]
                c.create_line(px(padre.x_centro), px(padre.y_centro + padre.h / 2),
                              px(p.x_centro), px(p.y_centro - p.h / 2),
                              fill=theme.EDGE, width=max(1, s))
        for i, p in enumerate(nodos):
            x0, y0 = px(p.x_centro - p.w / 2), px(p.y_centro - p.h / 2)
            x1, y1 = px(p.x_centro + p.w / 2), px(p.y_centro + p.h / 2)
            cx, cy = px(p.x_centro), px(p.y_centro)
            tag = f"n{i}"
            nodo = p.node
            if nodo.is_terminal:
                c.create_rectangle(x0, y0, x1, y1, fill=theme.TERMINAL_BG,
                                   outline=theme.NEON, width=max(1, s),
                                   tags=("terminal", tag))
                if con_texto:
                    c.create_text(cx, cy - 7 * s if con_tipo else cy, text=nodo.label,
                                  fill=theme.NEON, font=fuente, tags=("terminal", tag))
                if con_tipo:
                    c.create_text(cx, cy + 9 * s, text=nodo.symbol, fill=theme.MUTED,
                                  font=fuente_tipo, tags=("terminal", tag))
            elif nodo.is_epsilon:
                c.create_rectangle(x0, y0, x1, y1, fill=theme.BG,
                                   outline=theme.EPSILON_BORDER, dash=(3, 3), tags=(tag,))
                if con_texto:
                    c.create_text(cx, cy, text="ε", fill=theme.MUTED, font=fuente,
                                  tags=(tag,))
            else:
                c.create_rectangle(x0, y0, x1, y1, fill=theme.PANEL, outline=theme.CYAN,
                                   width=max(1, s), tags=(tag,))
                if con_texto:
                    c.create_text(cx, cy, text=nodo.label, fill=theme.CYAN, font=fuente,
                                  tags=(tag,))
        c.configure(scrollregion=(0, 0, (self.layout.width + 2 * MARGIN) * s,
                                  (self.layout.height + 2 * MARGIN) * s))
        self.zoom_label.configure(text=f"{round(s * 100)} %")

    # ------------------------------------------------------------------
    # Zoom y exportación
    # ------------------------------------------------------------------

    def _zoom(self, factor: float) -> None:
        nueva = min(MAX_SCALE, max(MIN_SCALE, self.scale * factor))
        if abs(nueva - self.scale) < 1e-9 or self.layout is None:
            return
        # Conserva la posición relativa de la vista.
        fx, fy = self.canvas.xview()[0], self.canvas.yview()[0]
        self.scale = nueva
        self._dibujar()
        self.canvas.xview_moveto(fx)
        self.canvas.yview_moveto(fy)

    def zoom_in(self) -> None:
        self._zoom(ZOOM_STEP)

    def zoom_out(self) -> None:
        self._zoom(1 / ZOOM_STEP)

    def fit(self) -> None:
        """Ajusta la escala para que el árbol entre en el área visible."""
        if self.layout is None:
            return
        ancho = max(self.canvas.winfo_width(), 100)
        alto = max(self.canvas.winfo_height(), 100)
        escala = min(ancho / (self.layout.width + 2 * MARGIN),
                     alto / (self.layout.height + 2 * MARGIN))
        self.scale = min(MAX_SCALE, max(MIN_SCALE, escala))
        self._dibujar()
        self._mostrar_raiz()

    def export_svg(self) -> None:
        if self.root_node is None:
            self.on_status("No hay árbol para exportar.")
            return
        ruta = filedialog.asksaveasfilename(
            title="Exportar árbol SVG", defaultextension=".svg",
            filetypes=[("SVG", "*.svg"), ("Todos los archivos", "*.*")])
        if ruta:
            Path(ruta).write_text(to_svg(self.root_node, theme="dark"), encoding="utf-8")
            self.on_status(f"Árbol SVG exportado a {ruta}")
