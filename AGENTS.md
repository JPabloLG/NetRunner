# AGENTS.md — Reglas permanentes de desarrollo de NetRunner Analyzer

Referencia obligatoria para cualquier sesión (humana o de un agente) que modifique este proyecto.

## Stack tecnológico

- Python 3.11 o superior.
- Solo biblioteca estándar. GUI con Tkinter (incluido en Python).
- `pytest` es la única dependencia externa, y solo para desarrollo y pruebas (`requirements-dev.txt`).

## Bibliotecas prohibidas

- Analizadores: PLY, Lark, ANTLR, PyParsing o cualquier otra de análisis léxico o sintáctico.
- GUI externas: CustomTkinter, PyQt, PySide, etc.
- `re` está prohibido en el núcleo (`netrunner/`). Solo se permite dentro de `netrunner/gui/`.
  El análisis léxico se hace exclusivamente con las tablas de los AFD (`afd_tables.py`).
- Prohibido `eval`, `exec`, `subprocess`, sockets y cualquier acceso a red.

## Separación núcleo / GUI

- El núcleo (`netrunner/*.py`) no importa Tkinter ni nada de `netrunner.gui`.
- La GUI (`netrunner/gui/`) consume el núcleo, nunca al revés.
- El núcleo debe poder probarse sin pantalla.

## NetRunner no se ejecuta

NetRunner Analyzer **solo analiza** (léxico + sintáctico) código simulado. No se construye
ningún intérprete: ninguna instrucción NetRunner tiene efecto real.

## Convenciones

- PEP 8. Módulos y funciones en `snake_case`, clases en `PascalCase`, constantes en `MAYUSCULAS`.
- Type hints en todas las funciones públicas.
- Modelos de datos con `dataclass` (congeladas cuando sean inmutables) y categorías con `Enum`.
- Nombres de tipos de token fijos: ver `TokenType` en `netrunner/tokens.py`.
- Comentarios, docstrings, mensajes de error y textos de interfaz **en español**.
- Código legible y fácil de explicar en una sustentación universitaria: preferir claridad a astucia.

## Estructura del proyecto

```
netrunner-app/
├── AGENTS.md, README.md, requirements-dev.txt, main.py, conftest.py
├── netrunner/           # núcleo (sin Tkinter, sin re)
│   ├── tokens.py        # TokenType, RESERVED_WORDS, Token
│   ├── diagnostics.py   # Diagnostic (LEXICO / SINTACTICO)
│   ├── afd_tables.py    # tablas de transición de los AFD
│   ├── lexer.py         # analizador léxico basado en AFD
│   ├── grammar.py       # gramática del lenguaje
│   ├── parser.py        # analizador sintáctico
│   ├── tree.py          # árbol sintáctico
│   ├── tree_layout.py   # cálculo de posiciones del árbol
│   ├── examples.py      # lista de ejemplos y read_example()
│   └── gui/             # interfaz Tkinter (theme, editor, panels, tree_canvas, app)
├── examples/            # programas .nr de ejemplo
└── tests/               # pruebas pytest
```

## Validación obligatoria

Al finalizar cada etapa ejecutar desde la raíz del proyecto:

```
python -m pytest
```

No se considera terminada una etapa con pruebas fallando.
