"""Editor de código con numeración de líneas, resaltado y marcas de error."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from netrunner.diagnostics import Diagnostic
from netrunner.gui import theme
from netrunner.tokens import Token, TokenType

# Tag de resaltado para cada tipo de token.
_TAGS: dict[TokenType, str] = {
    TokenType.TK_CMD: "tk_cmd",
    TokenType.HEX_ADDR: "tk_hex",
    TokenType.TK_NUM: "tk_num",
    TokenType.STRING: "tk_str",
    TokenType.COMENTARIO: "tk_comment",
    TokenType.TK_OP: "tk_op",
    TokenType.TK_DELIM: "tk_op",
    TokenType.TK_IZQ: "tk_op",
    TokenType.TK_DER: "tk_op",
    TokenType.TK_MAYOR: "tk_op",
    TokenType.TK_MENOR: "tk_op",
    TokenType.TK_IGUAL: "tk_op",
}
_TODOS_LOS_TAGS = tuple(sorted(set(_TAGS.values())))


class LineNumbers(tk.Canvas):
    """Columna lateral con los números de línea del editor."""

    def __init__(self, parent: tk.Misc, text: tk.Text, fonts: theme.Fonts) -> None:
        super().__init__(parent, width=48, background=theme.PANEL,
                         highlightthickness=0, borderwidth=0)
        self.text = text
        self.font = fonts.mono
        self.error_lines: set[int] = set()

    def redraw(self) -> None:
        """Dibuja los números de las líneas visibles."""
        self.delete("all")
        total = int(self.text.index("end-1c").split(".")[0])
        ancho = self.font.measure("9" * max(3, len(str(total)))) + 16
        if int(self.cget("width")) != ancho:
            self.configure(width=ancho)
        indice = self.text.index("@0,0")
        while True:
            info = self.text.dlineinfo(indice)
            if info is None:
                break
            linea = int(indice.split(".")[0])
            color = theme.RED if linea in self.error_lines else theme.MUTED
            self.create_text(ancho - 8, info[1], anchor="ne", text=str(linea),
                             fill=color, font=self.font)
            siguiente = self.text.index(f"{indice}+1line")
            if siguiente == indice:
                break
            indice = siguiente


class CodeEditor(ttk.Frame):
    """Editor de NetRunner basado en tk.Text."""

    def __init__(
        self,
        parent: tk.Misc,
        fonts: theme.Fonts,
        on_change: Callable[[], None] | None = None,
        on_cursor: Callable[[int, int], None] | None = None,
    ) -> None:
        super().__init__(parent, style="Panel.TFrame")
        self.on_change = on_change
        self.on_cursor = on_cursor

        self.text = tk.Text(
            self, undo=True, maxundo=-1, wrap="none", font=fonts.mono,
            background=theme.BG, foreground=theme.TEXT,
            insertbackground=theme.NEON, insertwidth=2,
            selectbackground=theme.SELECTION, selectforeground=theme.TEXT,
            inactiveselectbackground=theme.SELECTION,
            relief="flat", borderwidth=0, highlightthickness=0,
            padx=8, pady=6, tabs=(fonts.mono.measure("    "),),
        )
        self.lines = LineNumbers(self, self.text, fonts)
        barra_y = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        barra_x = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=self._al_desplazar(barra_y),
                            xscrollcommand=barra_x.set)

        self.lines.grid(row=0, column=0, sticky="ns")
        self.text.grid(row=0, column=1, sticky="nsew")
        barra_y.grid(row=0, column=2, sticky="ns")
        barra_x.grid(row=1, column=1, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        # Resaltado sintáctico
        self.text.tag_configure("tk_cmd", foreground=theme.CYAN, font=fonts.mono_bold)
        self.text.tag_configure("tk_hex", foreground=theme.MAGENTA)
        self.text.tag_configure("tk_num", foreground=theme.AMBER)
        self.text.tag_configure("tk_str", foreground=theme.NEON)
        self.text.tag_configure("tk_op", foreground="#e6edf7")
        self.text.tag_configure("tk_comment", foreground=theme.MUTED, font=fonts.mono_italic)
        # Errores
        self.text.tag_configure("error", background=theme.ERROR_BG, underline=True)
        try:
            self.text.tag_configure("error", underlinefg=theme.RED)  # Tk >= 8.6.11
        except tk.TclError:
            pass
        self.text.tag_raise("error")
        self.text.tag_raise("sel")

        self.text.bind("<Tab>", self._tab)
        self.text.bind("<<Modified>>", self._modificado)
        self.text.bind("<Configure>", lambda _e: self.lines.redraw())
        for evento in ("<KeyRelease>", "<ButtonRelease-1>"):
            self.text.bind(evento, self._cursor_movido, add="+")

    # ------------------------------------------------------------------
    # Eventos internos
    # ------------------------------------------------------------------

    def _al_desplazar(self, barra: ttk.Scrollbar) -> Callable[[str, str], None]:
        def actualizar(primero: str, ultimo: str) -> None:
            barra.set(primero, ultimo)
            self.lines.redraw()
        return actualizar

    def _tab(self, _evento: tk.Event) -> str:
        self.text.insert("insert", "    ")
        return "break"

    def _modificado(self, _evento: tk.Event) -> None:
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        self.lines.redraw()
        if self.on_change is not None:
            self.on_change()

    def _cursor_movido(self, _evento: tk.Event | None = None) -> None:
        if self.on_cursor is not None:
            linea = int(self.text.index("insert").split(".")[0])
            # Se cuenta con el texto de Python para que coincida con el lexer.
            col = len(self.text.get(f"{linea}.0", "insert")) + 1
            self.on_cursor(linea, col)

    # Tk 8.6 cuenta los caracteres fuera del plano básico de Unicode (por
    # ejemplo, emojis) como dos posiciones, mientras que el lexer cuenta uno.
    # Las líneas que los contienen necesitan una corrección del índice.

    def _lineas_astrales(self) -> dict[int, str]:
        """Líneas (número → texto) que contienen caracteres fuera del BMP."""
        return {
            numero: texto
            for numero, texto in enumerate(self.get_text().split("\n"), start=1)
            if any(ord(c) > 0xFFFF for c in texto)
        }

    @staticmethod
    def _indice(line: int, col: int, astrales: dict[int, str] | None = None) -> str:
        """Índice de Tk para una posición del lexer (línea y columna desde 1)."""
        desplazamiento = col - 1
        if astrales and line in astrales:
            desplazamiento += sum(1 for c in astrales[line][:col - 1] if ord(c) > 0xFFFF)
        return f"{line}.{desplazamiento}"

    def _rango(self, line: int, col: int, length: int,
               astrales: dict[int, str] | None = None) -> tuple[str, str]:
        """Índices de Tk de inicio y fin de un lexema de una sola línea."""
        return (self._indice(line, col, astrales),
                self._indice(line, col + max(length, 1), astrales))

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def get_text(self) -> str:
        """Contenido completo del editor."""
        return self.text.get("1.0", "end-1c")

    def set_text(self, contenido: str) -> None:
        """Reemplaza el contenido (reinicia el historial de deshacer)."""
        self.text.delete("1.0", "end")
        self.text.insert("1.0", contenido)
        self.text.edit_reset()
        self.text.mark_set("insert", "1.0")
        self.text.see("1.0")
        self.clear_marks()
        self.lines.redraw()
        self._cursor_movido()

    def highlight_tokens(self, tokens: list[Token]) -> None:
        """Colorea los tokens (se borran antes los colores anteriores)."""
        for tag in _TODOS_LOS_TAGS:
            self.text.tag_remove(tag, "1.0", "end")
        astrales = self._lineas_astrales()
        for token in tokens:
            tag = _TAGS.get(token.type)
            if tag is None or token.length == 0:
                continue
            self.text.tag_add(tag, *self._rango(token.line, token.col, token.length, astrales))

    def mark_errors(self, diagnostics: list[Diagnostic]) -> None:
        """Marca el rango de cada diagnóstico y su línea en la numeración."""
        self.text.tag_remove("error", "1.0", "end")
        astrales = self._lineas_astrales()
        for d in diagnostics:
            self.text.tag_add("error", *self._rango(d.line, d.col, d.length, astrales))
        self.lines.error_lines = {d.line for d in diagnostics}
        self.lines.redraw()

    def clear_marks(self) -> None:
        """Quita resaltado y marcas de error."""
        for tag in _TODOS_LOS_TAGS + ("error",):
            self.text.tag_remove(tag, "1.0", "end")
        self.lines.error_lines = set()
        self.lines.redraw()

    def select_range(self, line: int, col: int, length: int) -> None:
        """Selecciona y muestra un rango sin quitar el foco al widget actual."""
        inicio, fin = self._rango(line, col, length, self._lineas_astrales())
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", inicio, fin)
        self.text.mark_set("insert", inicio)
        self.text.see(inicio)
        self._cursor_movido()

    def goto(self, line: int, col: int, length: int) -> None:
        """Mueve el cursor, muestra y selecciona el rango, y da foco al editor."""
        self.select_range(line, col, length)
        self.text.focus_set()
