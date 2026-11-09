# NetRunner Analyzer

Analizador léxico y sintáctico de **NetRunner DSL**, desarrollado para la materia
**Teoría de Lenguajes Formales** — Ingeniería de Sistemas y Computación, Universidad del
Quindío, 2026-2.

---

## 1. Qué es NetRunner Analyzer

NetRunner DSL es un lenguaje de dominio específico para **describir** secuencias simuladas
de ciberataques: escaneo de red, evasión de defensas, inyección de código y limpieza de
huellas. Cada programa se organiza en objetivos (`TARGET NODE <dirección hexadecimal>`)
que contienen acciones y condicionales.

NetRunner Analyzer es una aplicación de escritorio (y de consola) que:

- realiza el **análisis léxico** con los cinco AFD diseñados en la Fase 1, implementados
  como tablas de transición explícitas (sin expresiones regulares);
- realiza el **análisis sintáctico** con un analizador **predictivo LL(1) por descenso
  recursivo**, construido sobre la gramática LL(1) de la Fase 2;
- calcula automáticamente **FIRST**, **FOLLOW** y la **tabla predictiva**;
- muestra tokens, trazas de los autómatas, el árbol de derivación (texto y gráfico) y los
  errores con su posición exacta.

> El programa **solo analiza** el código NetRunner. Nunca lo ejecuta: no hay intérprete.

## 2. Requisitos

- **Python 3.11 o superior.**
- **Tkinter** (incluido en los instaladores de Python para Windows y macOS).
  En Debian/Ubuntu se instala aparte:

  ```bash
  sudo apt install python3-tk
  ```

- **pytest**, solo para ejecutar las pruebas (única dependencia externa, de desarrollo).

No se usa ninguna otra biblioteca externa.

## 3. Instalación y ejecución

Desde la carpeta del proyecto:

```bash
python -m pip install -r requirements-dev.txt   # solo para las pruebas
```

| Comando | Qué hace |
|---|---|
| `python main.py` | Abre la interfaz gráfica (carga `examples/ok_1_completo.nr`) |
| `python main.py archivo.nr` | Abre la interfaz gráfica con ese archivo |
| `python main.py archivo.nr --cli` | Analiza en consola: imprime el árbol o los errores |
| `python main.py archivo.nr --cli --tokens` | Además imprime la tabla de tokens |
| `python main.py archivo.nr --cli --simplificar` | Muestra (y exporta) el árbol simplificado |
| `python main.py archivo.nr --cli --dot salida.dot --svg salida.svg` | Exporta el árbol a Graphviz y SVG |

Códigos de salida del modo consola: **0** análisis correcto, **1** errores léxicos o
sintácticos, **2** archivo inexistente o ilegible.

Formato de los errores en consola:

```
[Léxico] 2:16  Símbolo '@' no pertenece al alfabeto de NetRunner
[Sintáctico] 3:13  Se esperaba 'PORT', pero se encontró '22'
```

El modo consola no importa Tkinter, así que funciona aunque Tkinter no esté instalado.

## 4. Cómo usar la interfaz

La ventana se divide en el **editor** (izquierda) y los **resultados** (derecha). Encima de
los resultados hay un resumen: tokens, errores léxicos, errores sintácticos, nodos del árbol
y el veredicto (`CÓDIGO VÁLIDO`, `CÓDIGO CON ERRORES` o `SIN CÓDIGO`).

**Barra de herramientas:** Abrir archivo (Ctrl+O), Guardar (Ctrl+S), **Analizar** (F5 o
Ctrl+Enter), Limpiar, menú **Ejemplos** (carga y analiza cualquiera de los siete ejemplos) y
la casilla **Analizar al escribir** (analiza 600 ms después de dejar de escribir).

- **Editor.** Numeración de líneas, resaltado por tipo de token (palabras reservadas en
  cian, direcciones en magenta, números en ámbar, cadenas en verde, comentarios en cursiva
  atenuada), Tab inserta cuatro espacios. Los errores se marcan con fondo rojo oscuro y
  subrayado, y su número de línea aparece en rojo. La barra de estado muestra `Ln, Col`.
- **Tokens.** Tabla con número, línea, columna, tipo y lexema. La casilla *Mostrar espacios
  y comentarios* incluye los tokens auxiliares. Al seleccionar un token se resalta en el
  editor y aparece su **traza del AFD**: autómata usado, transiciones
  (`q0 —0→ q1 —x→ q3 —a→ q4`) y estado final (`q4 ∈ F → HEX_ADDR`). *Exportar CSV* guarda la
  tabla.
- **Árbol de derivación.** El árbol completo de la derivación LL(1) en forma jerárquica
  (no terminales en cian, terminales en verde, ε atenuado). *Simplificar*, *Expandir todo*,
  *Colapsar todo*, *Copiar como texto*, *Exportar .txt* y *Exportar .dot*. Al seleccionar
  una hoja se resalta su lexema en el editor.
- **Árbol gráfico.** El mismo árbol dibujado: *Zoom +*, *Zoom −*, *Ajustar*, *Exportar SVG*
  y *Simplificar* (compartido con la pestaña anterior). Rueda: desplazamiento vertical;
  Shift+rueda: horizontal; Ctrl+rueda: zoom (30 % a 300 %); arrastrar con el botón
  izquierdo: mover la vista; clic en un terminal: resaltarlo en el editor.
- **Errores.** Lista ordenada por posición; los léxicos en rojo y los sintácticos en ámbar.
  Al seleccionar uno (o con doble clic) el cursor salta a esa posición en el editor.
- **Gramática.** Gramática original, gramática LL(1), conjuntos FIRST y FOLLOW, y la tabla
  LL(1) (cada celda muestra el número de la producción; al seleccionar una fila se listan
  las producciones de ese no terminal). Al final indica *Gramática LL(1): sin conflictos*.

Si el código tiene errores, el árbol no se muestra y se abre automáticamente la pestaña
Errores.

## 5. Estructura del proyecto

```
netrunner-app/
├── AGENTS.md                  reglas permanentes de desarrollo
├── README.md                  este documento
├── requirements-dev.txt       pytest (solo desarrollo)
├── conftest.py                hace que pytest encuentre el paquete netrunner
├── main.py                    punto de entrada: GUI por defecto, consola con --cli
├── netrunner/                 núcleo (sin Tkinter ni expresiones regulares)
│   ├── __init__.py
│   ├── tokens.py              TokenType, las 23 RESERVED_WORDS y la dataclass Token
│   ├── diagnostics.py         Diagnostic (errores LEXICO / SINTACTICO)
│   ├── afd_tables.py          clases de símbolos, las 5 tablas de transición, trie, run_afd
│   ├── lexer.py               analizador léxico: elige el AFD y aplica máxima coincidencia
│   ├── grammar.py             gramáticas original y LL(1), FIRST, FOLLOW, tabla LL(1)
│   ├── parser.py              analizador LL(1) por descenso recursivo con recuperación
│   ├── tree.py                Node, simplificación y exportación ASCII / DOT / SVG
│   ├── tree_layout.py         posiciones del árbol (sin Tkinter), usado por SVG y Canvas
│   ├── examples.py            lista de ejemplos y read_example()
│   └── gui/                   interfaz Tkinter / ttk
│       ├── __init__.py
│       ├── theme.py           paleta oscura, fuentes y estilos ttk
│       ├── editor.py          editor con numeración, resaltado y marcas de error
│       ├── panels.py          resumen y pestañas Tokens, Árbol, Errores y Gramática
│       ├── tree_canvas.py     árbol gráfico con zoom y desplazamiento
│       └── app.py             ventana principal y flujo analyze()
├── examples/                  los siete programas de ejemplo (.nr)
│   ├── ok_1_completo.nr
│   ├── ok_2_minimo.nr
│   ├── ok_3_anidado.nr
│   ├── error_1_mixto.nr
│   ├── error_2_lexico.nr
│   ├── error_3_falta_llave.nr
│   └── error_4_if_sin_then.nr
└── tests/                     pruebas pytest
    ├── test_afd_tables.py     tablas, trie (111 estados), determinismo, run_afd
    ├── test_lexer.py          tokens, mensajes de error, posiciones, trazas
    ├── test_grammar.py        FIRST, FOLLOW, tabla LL(1), conflictos
    ├── test_parser.py         programas válidos, errores, recuperación, robustez
    ├── test_tree.py           árbol, simplificación, layout, DOT y SVG
    ├── test_cli.py            main.py --cli (subprocess), exportaciones, sin Tkinter
    └── test_gui_smoke.py      prueba de humo de la interfaz
```

## 6. Correspondencia con la Fase 1

La Fase 1 (Formalismo léxico) definió el alfabeto, las categorías léxicas y cinco AFD que
comparten el estado inicial `q0`. Cada tabla del documento corresponde a un objeto de
`netrunner/afd_tables.py`:

| Tabla PDF | Implementación |
|---|---|
| Tabla 1 — palabras reservadas | Trie `KEYWORD_AFD` y `KEYWORD_ACCEPT`, generados por `build_keyword_afd(RESERVED_WORDS)` |
| Tabla 2 — enteros y hexadecimales | `NUM_AFD` y `NUM_ACCEPT` |
| Tabla 3 — cadenas de texto | `STR_AFD` y `STR_ACCEPT` |
| Tabla 4 — operadores y delimitadores | `OPS_AFD` y `OPS_ACCEPT` |
| Tabla 5 — comentarios y espacios | `WS_AFD` y `WS_ACCEPT` |

- Cada familia es un `AFDFamily` (`KEYWORD_FAMILY`, `NUM_FAMILY`, `STR_FAMILY`,
  `OPS_FAMILY`, `WS_FAMILY`) con su nombre, tabla, estados de aceptación y clasificador de
  símbolos.
- Las clases de símbolos (`ZERO`, `NZ`, `X`, `HEXL`, `BLANK`, `NOT_NL`, `ANY_STR`) son
  conjuntos ASCII explícitos.
- El trie tiene exactamente **111 estados sin contar q0**, igual que en el documento; cada
  estado se llama como el prefijo leído (`T`, `TA`, `TAR`, …).
- `run_afd` recorre la tabla carácter a carácter, guarda la traza real
  `(estado, carácter, destino)` y recuerda el último estado de aceptación (máxima
  coincidencia con retroceso).
- **Determinismo:** los símbolos con transición desde `q0` de las cinco familias son
  disjuntos dos a dos (lo comprueba `tests/test_afd_tables.py`), por lo que su unión es un
  único AFD determinista.

## 7. Correspondencia con la Fase 2

`netrunner/grammar.py` contiene las dos gramáticas como listas de producciones
`(izquierda, [derecha])` y los algoritmos de punto fijo.

**Gramática original** (`ORIGINAL_GRAMMAR`, 11 no terminales, 28 alternativas). Tiene
recursividad por la izquierda (`<programa> ::= <programa> <objetivo>`,
`<lista_sent> ::= <lista_sent> <sentencia>`, `<secuencia> ::= <secuencia> -> <accion>`) y
prefijos comunes (`SCAN PORTS | SCAN PORT TK_NUM`, `IF … THEN <bloque> | IF … THEN <bloque>
ELSE <bloque>`). Por eso su tabla predictiva tiene conflictos.

**Eliminación de la recursividad por la izquierda.** `A ::= A α | β` se reemplaza por
`A ::= β A'` y `A' ::= α A' | ε`. Así aparecen `<programa'>`, `<lista_sent'>` y
`<secuencia'>`.

**Factorización por la izquierda.** Las alternativas con prefijo común se separan:
`<accion> ::= SCAN <accion'>` con `<accion'> ::= PORTS | PORT TK_NUM`, y
`<condicional> ::= IF <condicion> THEN <bloque> <condicional'>` con
`<condicional'> ::= ELSE <bloque> | ε`.

**Gramática LL(1)** (`LL1_GRAMMAR`, 16 reglas numeradas, 33 alternativas):

```
 1. <programa>      ::= <objetivo> <programa'>
 2. <programa'>     ::= <objetivo> <programa'> | ε
 3. <objetivo>      ::= TARGET NODE HEX_ADDR <bloque>
 4. <bloque>        ::= { <lista_sent> }
 5. <lista_sent>    ::= <sentencia> <lista_sent'>
 6. <lista_sent'>   ::= <sentencia> <lista_sent'> | ε
 7. <sentencia>     ::= <secuencia> ; | <condicional>
 8. <secuencia>     ::= <accion> <secuencia'>
 9. <secuencia'>    ::= -> <accion> <secuencia'> | ε
10. <accion>        ::= SCAN <accion'> | CONNECT PORT TK_NUM | BYPASS FIREWALL
                      | DISABLE FIREWALL | INJECT PAYLOAD STRING
                      | EXECUTE SCRIPT STRING | EXFIL DATA | CLEAR LOGS
11. <accion'>       ::= PORTS | PORT TK_NUM
12. <condicional>   ::= IF <condicion> THEN <bloque> <condicional'>
13. <condicional'>  ::= ELSE <bloque> | ε
14. <condicion>     ::= ICE_LEVEL <comp> TK_NUM | FIREWALL == <estado>
15. <comp>          ::= > | < | ==
16. <estado>        ::= ACTIVE | INACTIVE
```

Las alternativas se numeran `2a`, `2b`, `10a` … `10h`, etc.

**FIRST** (`compute_first`): punto fijo. Se parte de conjuntos vacíos y se agrega
FIRST(lado derecho) a FIRST(lado izquierdo) hasta que nada cambia; `first_of_sequence`
recorre los símbolos mientras sean anulables y agrega ε si todos lo son.

**FOLLOW** (`compute_follow`): punto fijo. `$ ∈ FOLLOW(<programa>)`; para cada
`A ::= α B β` se agrega FIRST(β) − {ε} a FOLLOW(B) y, si β es anulable, FOLLOW(A).

**Tabla predictiva** (`build_ll1_table`): para `A ::= α`, `M[A, a] = α` por cada `a` en
FIRST(α); si ε ∈ FIRST(α), también por cada `b` en FOLLOW(A). `find_conflicts` detecta
celdas con dos o más producciones: la gramática LL(1) tiene **0 conflictos**; la original
sí tiene (por ejemplo `M[<accion>, SCAN]`).

**Analizador** (`netrunner/parser.py`): un método por no terminal (`_programa`,
`_objetivo`, `_bloque`, `_lista_sent`, `_sentencia`, `_secuencia`, `_accion`, `_accion_p`,
`_condicional`, `_condicional_p`, `_condicion`, `_comp`, `_estado`). Decide mirando solo el
token actual con los FIRST/FOLLOW calculados, sin retroceso.

## 8. Lenguaje NetRunner: referencia rápida

**Palabras reservadas (23, siempre en MAYÚSCULAS):**
`TARGET NODE IF THEN ELSE SCAN PORTS CONNECT PORT BYPASS ICE_LEVEL DISABLE FIREWALL ACTIVE
INACTIVE INJECT PAYLOAD EXECUTE SCRIPT EXFIL DATA CLEAR LOGS`

No existen identificadores: cualquier otra palabra es un error léxico.

**Tokens:**

| Token | Ejemplo | Descripción |
|---|---|---|
| `TK_CMD` | `SCAN` | palabra reservada |
| `TK_NUM` | `8080`, `0`, `007` | entero sin signo |
| `HEX_ADDR` | `0xad23d` | `0x` seguido de uno o más dígitos hexadecimales |
| `STRING` | `"recon.sh"` | cadena entre comillas rectas, en una sola línea |
| `TK_OP` | `->` | operador de flujo |
| `TK_DELIM` | `;` | fin de instrucción |
| `TK_IZQ`, `TK_DER` | `{`, `}` | inicio y fin de bloque |
| `TK_MAYOR`, `TK_MENOR`, `TK_IGUAL` | `>`, `<`, `==` | comparación |
| `COMENTARIO` | `// texto` | hasta el fin de línea (auxiliar) |
| `ESPACIO` | espacios, tabs, saltos | auxiliar |

**Estructura de un objetivo.** Un programa tiene uno o más objetivos; cada bloque tiene al
menos una sentencia:

```
TARGET NODE 0xad23d {
    sentencia
    ...
}
```

**Acciones** (se encadenan con `->` y la secuencia termina en `;`):

```
SCAN PORTS            SCAN PORT 8080        CONNECT PORT 22
BYPASS FIREWALL       DISABLE FIREWALL
INJECT PAYLOAD "x"    EXECUTE SCRIPT "x"
EXFIL DATA            CLEAR LOGS

SCAN PORTS -> EXFIL DATA -> CLEAR LOGS;
```

**Condicionales** (el `ELSE` es opcional; se pueden anidar):

```
IF <condición> THEN { ... }
IF <condición> THEN { ... } ELSE { ... }
```

**Condiciones:**

```
ICE_LEVEL > 3     ICE_LEVEL < 3     ICE_LEVEL == 3
FIREWALL == ACTIVE                  FIREWALL == INACTIVE
```

**Comentarios:** `// hasta el final de la línea`.

**Ejemplo completo:**

```
// Ataque simulado
TARGET NODE 0xad23d {
    SCAN PORTS -> SCAN PORT 8080;
    IF FIREWALL == ACTIVE THEN {
        BYPASS FIREWALL -> INJECT PAYLOAD "rootkit.bin";
    } ELSE {
        EXECUTE SCRIPT "recon.sh";
    }
    EXFIL DATA -> CLEAR LOGS;
}
```

## 9. Ejecutar las pruebas

```bash
python -m pip install -r requirements-dev.txt
pytest
```

Si el comando `pytest` no está en el PATH (frecuente en Windows cuando pip instala en la
carpeta del usuario), use el equivalente `python -m pytest`.

Las pruebas de la interfaz se omiten automáticamente si no hay pantalla disponible. Las
pruebas que dependen del contenido de los archivos de `examples/` se omiten mientras esos
archivos estén vacíos.

## 10. Decisiones de diseño

**Análisis léxico**

1. **El operador `<` fue añadido como q18.** La Tabla 4 de la Fase 1 no tenía estado para
   `<`; se agregó `"<": "q18"` en `OPS_AFD` con `q18 → TK_MENOR`.
2. **`007` es aceptado como entero.** En la Tabla 2, desde `q1` (el `0`) un dígito lleva a
   `q2`, que es de aceptación; `0` solo también es `TK_NUM`.
3. **Regla de frontera de lexema.** Ante una letra, dígito o `_` se extrae el candidato
   máximo `[A-Za-z0-9_]` y el AFD debe aceptarlo **completo**. `SCANS`, `PORT22` o `22abc`
   producen un único error y nunca se dividen en varios tokens.
4. **Las cadenas son de una sola línea** y no tienen secuencias de escape. Una cadena sin
   cierre se informa en la comilla de apertura y se consume hasta antes del salto de línea.
5. **Comentarios y espacios no llegan al parser.** Están en `all_tokens` (para la
   interfaz) pero no en `tokens`.
6. **Los lexemas inválidos no generan tokens.** El primer token válido después de un error
   léxico lleva `after_lex_error=True`, y si provoca un error sintáctico el mensaje añade
   *(posible consecuencia de un error léxico anterior)*.
7. **El árbol no se muestra cuando existen errores** (léxicos o sintácticos): el parser
   devuelve `tree=None`.
8. Orden de decisión para palabras inválidas: primero *MAYÚSCULAS* (`scan` → `SCAN`), luego
   *palabra reservada incompleta* (el trie leyó todo el candidato sin morir, pero terminó en
   un estado no final, como `SCA`), luego *palabra no reconocida*. Los mensajes de números
   también salen del estado donde se detuvo el AFD de la Tabla 2: muerto en `q3` al final
   → hexadecimal incompleto; muerto en `q3`/`q4` antes del final → carácter hexadecimal
   inválido; cualquier otro caso → número mal formado.
9. Se detectan caracteres pegados desde procesadores de texto: guiones tipográficos
   (`– — − ‐ ‑ ‒`) y comillas tipográficas (`“ ” „ ‟ ‘ ’`) tienen mensajes propios.
10. Líneas y columnas empiezan en 1; un tabulador cuenta una columna. EOF se ubica justo
    después del último carácter.
11. La traza de cada token conserva el carácter real leído, no el nombre de su clase.
12. En archivos con saltos de línea de Windows (`\r\n`), el `\r` final queda dentro del
    lexema del comentario, porque `NOT_NL` solo excluye `\n`.

**Gramática y análisis sintáctico**

13. La tabla LL(1) guarda el índice de la alternativa; el número que se muestra (`10a`) se
    deriva del orden de los no terminales.
14. Los no terminales recursivos por la derecha (`<programa'>`, `<lista_sent'>`,
    `<secuencia'>`) se analizan con bucles `while`, pero el árbol conserva la estructura
    anidada. Así se analizan 2000 sentencias sin `RecursionError`.
15. Mecanismo *expected*: cada `check` fallido anota el terminal esperado y `advance` vacía
    el conjunto; así los mensajes enumeran exactamente las alternativas válidas. Si están
    los nueve terminales de FIRST(sentencia) se resumen como "una instrucción". Los
    esperados se listan en el orden de aparición en la gramática.
16. Recuperación en modo pánico: a nivel de sentencia (hasta `;`, `}`, FIRST(sentencia) o
    EOF), a nivel de objetivo (hasta `TARGET` o EOF), y para tokens fuera de un objetivo.
    Como máximo 100 diagnósticos y nunca dos en la misma posición.
17. Un `IF` sin `THEN` produce dos errores: el propio y uno en cascada por la `}` final,
    porque la recuperación cierra el bloque antes de tiempo. Es el comportamiento normal
    del modo pánico.

**Árbol, consola e interfaz**

18. Todas las operaciones sobre el árbol (recorridos, simplificación, ASCII, DOT, SVG,
    layout) son iterativas para soportar árboles muy profundos.
19. `simplify` devuelve una copia: elimina ε, sustituye los no terminales `<x'>` por sus
    hijos y elimina no terminales vacíos; la frontera del árbol no cambia.
20. El layout reserva a cada subárbol un tramo horizontal propio y centra al padre sobre
    sus hijos, así las cajas de un mismo nivel nunca se solapan.
21. `main.py` solo importa Tkinter al abrir la GUI; en Windows activa la conciencia de DPI y
    fuerza UTF-8 en la consola (para `├──` y `ε`).
22. La GUI usa una sola instancia de `Tk`. Al cargar un ejemplo, *Guardar* pide una ruta
    nueva para no sobrescribir los ejemplos.
23. El análisis se ejecuta en el hilo principal de Tkinter. Para que no bloquee más de lo
    necesario, el árbol gráfico (lo más costoso: miles de figuras) solo se dibuja cuando su
    pestaña se muestra, y cada etiqueta se mide una sola vez. Un programa de 2000
    sentencias se analiza y presenta en unos 2 segundos.
24. Tk 8.6 cuenta los caracteres fuera del plano básico de Unicode (emojis) como dos
    posiciones, y el lexer como una. El editor corrige el índice en esas líneas para que el
    resaltado, las marcas de error y la posición `Ln, Col` coincidan con el lexer.
25. El parser recursivo se verifica contra un analizador LL(1) de pila dirigido por la
    tabla de `grammar.py`: en programas generados aleatoriamente desde la gramática ambos
    construyen el mismo árbol, y en programas mutados aceptan exactamente lo mismo.
