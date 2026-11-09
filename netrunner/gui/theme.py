"""Tema visual oscuro estilo hacker (negro, verde neón y cian) para ttk."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from tkinter import ttk

# --- Paleta -------------------------------------------------------------------

BG = "#0a0e14"
PANEL = "#0f1520"
PANEL_2 = "#131c2b"
BORDER = "#1f2d44"
TEXT = "#c9d6e8"
MUTED = "#6b7a90"
NEON = "#00ff9c"
CYAN = "#00d9ff"
MAGENTA = "#ff4fd8"
AMBER = "#ffb86b"
RED = "#ff4d6d"
ERROR_BG = "#3a0f1a"
SELECTION = "#1f3b5c"

# Colores propios del árbol gráfico.
TERMINAL_BG = "#0f2a1f"
EDGE = "#3a5070"
EPSILON_BORDER = "#5a6578"

MONO_PREFERENCES = (
    "Cascadia Mono",
    "Consolas",
    "JetBrains Mono",
    "DejaVu Sans Mono",
    "Menlo",
    "Courier New",
)


@dataclass(frozen=True)
class Fonts:
    """Fuentes de la aplicación (todas monoespaciadas)."""

    family: str
    mono: tkfont.Font
    mono_bold: tkfont.Font
    mono_italic: tkfont.Font
    small: tkfont.Font
    ui: tkfont.Font
    ui_bold: tkfont.Font
    title: tkfont.Font


def pick_mono_family(root: tk.Misc) -> str:
    """Primera fuente monoespaciada disponible según MONO_PREFERENCES."""
    disponibles = set(tkfont.families(root))
    for familia in MONO_PREFERENCES:
        if familia in disponibles:
            return familia
    return "Courier"


def _fixed_map(style: ttk.Style, option: str) -> list[tuple[str, ...]]:
    """Parche de Treeview: sin él, Tk 8.6.9+ ignora los colores de los tags."""
    return [
        elemento for elemento in style.map("Treeview", query_opt=option)
        if elemento[:2] != ("!disabled", "!selected")
    ]


def setup_theme(root: tk.Tk) -> Fonts:
    """Configura ttk.Style (tema clam) y devuelve las fuentes."""
    familia = pick_mono_family(root)
    fonts = Fonts(
        family=familia,
        mono=tkfont.Font(root, family=familia, size=10),
        mono_bold=tkfont.Font(root, family=familia, size=10, weight="bold"),
        mono_italic=tkfont.Font(root, family=familia, size=10, slant="italic"),
        small=tkfont.Font(root, family=familia, size=8),
        ui=tkfont.Font(root, family=familia, size=9),
        ui_bold=tkfont.Font(root, family=familia, size=9, weight="bold"),
        title=tkfont.Font(root, family=familia, size=22, weight="bold"),
    )
    root.configure(background=BG)
    # Nota: no se usa option_add("*Font") porque anularía la fuente de los
    # estilos ttk (por ejemplo, el título de 22 puntos).
    root.option_add("*Menu.font", fonts.ui)
    root.option_add("*Menu.background", PANEL_2)
    root.option_add("*Menu.foreground", TEXT)
    root.option_add("*Menu.activeBackground", SELECTION)
    root.option_add("*Menu.activeForeground", NEON)
    root.option_add("*Menu.relief", "flat")

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    troughcolor=PANEL, focuscolor=CYAN, font=fonts.ui,
                    selectbackground=SELECTION, selectforeground=TEXT)

    # Marcos y etiquetas
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("Header.TFrame", background=PANEL)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
    style.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
    style.configure("Title.TLabel", background=PANEL, foreground=NEON, font=fonts.title)
    style.configure("Ok.TLabel", background=BG, foreground=NEON, font=fonts.ui_bold)
    style.configure("Bad.TLabel", background=BG, foreground=RED, font=fonts.ui_bold)
    style.configure("Status.TLabel", background=PANEL, foreground=MUTED,
                    font=fonts.small, padding=(8, 3))
    style.configure("Section.TLabel", background=BG, foreground=CYAN, font=fonts.ui_bold)

    # Botones
    style.configure("TButton", background=PANEL_2, foreground=TEXT, bordercolor=BORDER,
                    lightcolor=PANEL_2, darkcolor=PANEL_2, padding=(8, 3),
                    focusthickness=0, relief="flat")
    style.map("TButton",
              background=[("pressed", SELECTION), ("active", BORDER)],
              foreground=[("pressed", NEON), ("active", CYAN)],
              bordercolor=[("active", CYAN)])
    style.configure("Tool.TButton", padding=(6, 2))
    style.configure("Accent.TButton", background=NEON, foreground=BG,
                    lightcolor=NEON, darkcolor=NEON, bordercolor=NEON, font=fonts.ui_bold)
    style.map("Accent.TButton",
              background=[("pressed", "#00b36e"), ("active", "#5cffc0")],
              foreground=[("pressed", BG), ("active", BG)],
              bordercolor=[("active", "#5cffc0")])

    # Menubutton (menú Ejemplos)
    style.configure("TMenubutton", background=PANEL_2, foreground=TEXT, bordercolor=BORDER,
                    lightcolor=PANEL_2, darkcolor=PANEL_2, arrowcolor=CYAN, padding=(10, 4))
    style.map("TMenubutton",
              background=[("pressed", SELECTION), ("active", BORDER)],
              foreground=[("pressed", NEON), ("active", CYAN)])

    # Checkbutton
    for nombre, fondo in (("TCheckbutton", BG), ("Panel.TCheckbutton", PANEL)):
        style.configure(nombre, background=fondo, foreground=TEXT,
                        indicatorbackground=PANEL_2, indicatorforeground=NEON,
                        indicatorrelief="flat", focusthickness=0)
        style.map(nombre,
                  background=[("active", fondo)],
                  foreground=[("active", CYAN)],
                  indicatorbackground=[("selected", SELECTION), ("pressed", BORDER)])

    # Notebook
    style.configure("TNotebook", background=BG, bordercolor=BORDER, tabmargins=(4, 4, 4, 0))
    style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED,
                    bordercolor=BORDER, lightcolor=PANEL, padding=(9, 4))
    style.map("TNotebook.Tab",
              background=[("selected", PANEL_2), ("active", BORDER)],
              foreground=[("selected", NEON), ("active", CYAN)],
              lightcolor=[("selected", NEON)])

    # Treeview
    alto_fila = fonts.mono.metrics("linespace") + 6
    style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                    foreground=TEXT, bordercolor=BORDER, rowheight=alto_fila,
                    font=fonts.mono)
    style.configure("Treeview.Heading", background=PANEL_2, foreground=CYAN,
                    bordercolor=BORDER, lightcolor=PANEL_2, darkcolor=PANEL_2,
                    relief="flat", font=fonts.ui_bold, padding=(6, 4))
    style.map("Treeview.Heading",
              background=[("pressed", SELECTION), ("active", BORDER)],
              foreground=[("active", NEON)])
    style.map("Treeview",
              background=[("selected", SELECTION)] + _fixed_map(style, "background"),
              foreground=[("selected", NEON)] + _fixed_map(style, "foreground"))

    # Scrollbars
    for orient in ("Vertical", "Horizontal"):
        style.configure(f"{orient}.TScrollbar", background=PANEL_2, troughcolor=BG,
                        bordercolor=BG, lightcolor=PANEL_2, darkcolor=PANEL_2,
                        arrowcolor=MUTED, gripcount=0)
        style.map(f"{orient}.TScrollbar",
                  background=[("pressed", SELECTION), ("active", BORDER)],
                  arrowcolor=[("active", CYAN)])

    # Paneles divididos
    style.configure("TPanedwindow", background=BG)
    style.configure("Sash", sashthickness=6, gripcount=0, background=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER)
    return fonts


def readonly_text(parent: tk.Misc, fonts: Fonts, **kw: object) -> tk.Text:
    """Text de solo lectura con los colores del tema."""
    texto = tk.Text(parent, background=PANEL, foreground=TEXT, font=fonts.mono,
                    relief="flat", borderwidth=0, highlightthickness=0,
                    insertbackground=NEON, selectbackground=SELECTION,
                    padx=10, pady=8, wrap="none", **kw)
    texto.configure(state="disabled")
    return texto


def set_readonly_text(texto: tk.Text, contenido: str) -> None:
    """Reemplaza el contenido de un Text de solo lectura."""
    texto.configure(state="normal")
    texto.delete("1.0", "end")
    texto.insert("1.0", contenido)
    texto.configure(state="disabled")


def column_width(fonts: Fonts, titulo: str, minimo: int) -> int:
    """Ancho de columna suficiente para que el encabezado no se corte."""
    return max(minimo, fonts.ui_bold.measure(titulo) + 28)
