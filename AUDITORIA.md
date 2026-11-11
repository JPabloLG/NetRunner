# Auditoría técnica — NetRunner Analyzer (Fase 3)

- **Fecha:** 2026-11-11
- **Commit auditado:** `a28db72` (rama `main`, árbol limpio; `docs/` sin versionar)
- **Referencia:** `docs/NetRunner_Fase2_Fase3.pdf` (gramática G2, R1–R28, Tablas 7–15)
- **Entorno:** Windows 11, Python 3.14.0, pytest
- **Alcance:** solo lectura. No se modificó ningún archivo del proyecto; los casos de prueba se crearon en `/tmp/netrunner_cp/`.

---

## (a) Resumen ejecutivo

El analizador funciona y está bien construido: el léxico usa de verdad tablas de AFD, el parser es descendente recursivo LL(1) sin retroceso, construye el árbol de derivación con nodos primados y ε, reporta errores léxicos y sintácticos con línea y columna, y se recupera en modo pánico. Las 230 pruebas propias pasan y los 13 casos del plan de pruebas dan el resultado esperado.

**El problema principal no es de calidad sino de correspondencia: el código implementa una gramática distinta a la G2 del documento.** Esa gramática acepta un lenguaje más grande (varios `TARGET` y la acción `SCAN PORT NUM`), y además tiene otros nombres de no terminales y otra numeración (16 reglas con `10a`, `10b`… en lugar de R1–R28). El ejemplo que la GUI carga al iniciar (`examples/ok_1_completo.nr`) **no se puede derivar con G2**.

| Criterio de la rúbrica | Veredicto | Evidencia |
|---|---|---|
| Maneja errores léxicos | **Cumple** | 6/6 tipos de error de la especificación detectados con línea:columna (`netrunner/lexer.py:113-205`, `:236-240`) |
| Maneja errores sintácticos | **Cumple** | Mensaje “se esperaba X, pero se encontró Y” + modo pánico (`netrunner/parser.py:161-174`, `:189-223`) |
| Genera el árbol de derivación | **Cumple** | `Node` + `to_ascii` (`netrunner/tree.py:20`, `:146`); incluye primados y ε |
| Sin “hardcodeo” | **Cumple, con observaciones** | La ruta del archivo llega por argumento (`main.py:51`, `:92`); no hay rutas absolutas ni `re` en el núcleo. Observaciones: la tabla `ACCIONES_SIMPLES` copia la gramática a mano (`parser.py:48-56`) y la GUI carga un ejemplo fijo al abrir (`gui/app.py:33`, `:65`) |
| Acoplado a la gramática entregada (G2) | **Parcial / Difiere** | El código sigue su propia `LL1_GRAMMAR` (`grammar.py:57-107`): 16 no terminales frente a 13, 33 alternativas frente a 28, dos producciones que no están en G2 y nombres distintos. Ver §(c) |

**Pruebas:** `python -m pytest` → **230 passed** en 6,3 s. Casos CP-01…CP-13: **13/13 con el resultado esperado** (aceptado o rechazado, y el tipo de error). En CP-07 y CP-13 aparecen errores en cascada adicionales (ver §(b).3).

---

## 1. Inventario

| Elemento | Detalle |
|---|---|
| Punto de entrada | `main.py` → `main()` (`main.py:167`). **Sin `--cli` abre la GUI** (`main.py:176-178`) |
| Ejecución en consola | `python main.py archivo.nr --cli [--tokens] [--simplificar] [--dot X.dot] [--svg X.svg]` |
| Códigos de salida | 0 válido, 1 con errores, 2 archivo inexistente o ilegible (`main.py:24-26`) |
| Núcleo (`netrunner/`) | `tokens.py` (94 líneas), `afd_tables.py` (337), `lexer.py` (240), `grammar.py` (352), `parser.py` (369), `tree.py` (267), `tree_layout.py` (124), `diagnostics.py` (27), `examples.py` (33) |
| GUI (`netrunner/gui/`) | `app.py`, `editor.py`, `panels.py`, `theme.py`, `tree_canvas.py` (≈1 565 líneas en total, Tkinter) |
| Pruebas | 7 archivos en `tests/` (≈1 630 líneas, 230 pruebas) |
| Dependencias | Solo biblioteca estándar; `pytest` para desarrollo (`requirements-dev.txt`) |
| Restricciones verificadas | No hay `import re` en ningún archivo (tampoco en la GUI). No hay `eval`/`exec`/sockets. `subprocess` aparece **solo** en `tests/test_cli.py:3` |
| Higiene del repositorio | **Hay `__pycache__/*.pyc` versionados en git** (8 en `netrunner/`, 6 en `netrunner/gui/`) y no existe `.gitignore`. `docs/` no está versionado |

---

## (b) Tablas

### (b).1 Paso 2 — Análisis léxico frente a la especificación

La implementación usa **AFD con tablas de transición explícitas** (`afd_tables.py`) y un recorrido genérico con máxima coincidencia y retroceso (`run_afd`, `afd_tables.py:240-284`). Son cinco AFD con `q0` compartido; sus símbolos iniciales son disjuntos, así que la unión es determinista (lo verifica `tests/test_afd_tables.py`).

| Elemento de la especificación | Implementación (archivo:línea) | Estado | Observación |
|---|---|---|---|
| 23 palabras reservadas en MAYÚSCULA | `tokens.py:29-34`; trie `build_keyword_afd` `afd_tables.py:177-199` | Cumple | Trie de 111 estados sin `q0` (igual que en la Fase 1). Todas producen el tipo `TK_CMD`; el terminal de la gramática es el lexema (`tokens.py:92-93`) |
| `NUM` entero sin signo | `NUM_AFD` q0→q1/q2 `afd_tables.py:102-115` | Cumple | El token se llama `TK_NUM` y G2 lo llama `NUM`. Acepta ceros a la izquierda (`007`) |
| `HEX_ADDR` = `0x` + hex+ | `NUM_AFD` q1→q3→q4 `afd_tables.py:104-107`, `:114` | Cumple | Solo `x` minúscula: `0X1F` es error (“Número mal formado”) |
| `STRING` `"..."` | `STR_AFD` q5/q6 `afd_tables.py:121-126` | Cumple | Una sola línea: el salto de línea no tiene transición (`classify_str`, `afd_tables.py:75-76`). Sin secuencias de escape |
| `->` `==` `>` `<` `{` `}` `;` | `OPS_AFD` `afd_tables.py:132-154` | Cumple | `<` se agregó como q18 (`:140`, `:153`): es el ajuste que pide el PDF en §5 |
| Comentario `//` y espacios se descartan | `WS_AFD` `afd_tables.py:160-170`; filtro `lexer.py:227-234` | Cumple | Se guardan en `all_tokens` para la GUI, pero no llegan al parser |
| Lexema más largo (PORTS ≠ PORT+S) | `run_afd` `afd_tables.py:259-274` | Cumple | Verificado: `PORTS PORT` → `[PORTS, PORT]` |
| Error: símbolo fuera del alfabeto (`@`, `#`) | `_error_simbolo` `lexer.py:194-205` | Cumple | CP-11: `[Léxico] 1:24 Símbolo '@' no pertenece al alfabeto de NetRunner` |
| Error: minúsculas | `_mensaje_palabra` `lexer.py:185-188` | Cumple | CP-12: `Las palabras reservadas van en MAYÚSCULAS: 'scan' → 'SCAN'` |
| Error: `=` solo | `_leer_operador` `lexer.py:135-139` | Cumple | CP-13: `'=' solo no es un token; ¿quisiste escribir '=='?` |
| Error: `-` solo | `lexer.py:135-136` | Cumple | `'-' solo no es un token; ¿quisiste escribir '->'?` |
| Error: `0x` sin dígitos | `_mensaje_numero` `lexer.py:172-175` | Cumple | `Dirección hexadecimal incompleta: tras '0x' debe haber al menos un dígito hexadecimal` |
| Error: cadena sin cerrar | `_leer_cadena` `lexer.py:126-128` | Cumple | `Cadena sin cerrar: falta la comilla de cierre` |
| Línea y columna en los errores | `Diagnostic` `diagnostics.py:13-27`; `_error` `lexer.py:236-240` | Cumple | Base 1; un tabulador cuenta como una columna |
| Continúa después de un error léxico | `tokenize` `lexer.py:83-97` | Cumple | Reporta todos los errores léxicos de una sola vez |

**Diferencias respecto al AFD “puro”:**

1. **Regla de frontera del candidato** (`lexer.py:142-162`). Ante una letra, un dígito o `_`, primero se extrae el bloque máximo `[A-Za-z0-9_]` y se exige que el AFD lo acepte **completo**. Con maximal munch estricto, `22abc` daría `NUM(22)` y luego un error en `abc`; el código da un único error (“Número mal formado '22abc'”). `SCANPORTS` también da un solo error. Es una decisión razonable y está documentada (README §10.3), pero no aparece en el PDF.
2. **La familia se elige con `if` sobre el primer carácter** (`lexer.py:85-97`). Equivale a la transición desde `q0` del AFD unión, pero está escrita como `if` y no como una consulta a la tabla (salvo los operadores, `:91`).
3. Mensajes que no pide la especificación: `/` solo (`lexer.py:118`), `.` “pertenece al alfabeto” (`:196-197`), guiones y comillas tipográficas (`:30-31`, `:198-202`).

### (b).2 Paso 3 — Reglas R1–R28 frente al código

El parser es **descendente recursivo, con un método por no terminal** (`parser.py:229-369`), **sin recursión por la izquierda** y **sin retroceso**. Cada decisión usa solo el token actual (`Parser.tok`, `parser.py:124-126`), comparado con los conjuntos FIRST/FOLLOW que `grammar.py` **calcula** (`parser.py:33-45`). Los no terminales primados recursivos por la derecha se recorren con `while`, pero el árbol conserva el anidamiento.

La tabla LL(1) del código se calcula con `build_ll1_table` y **no tiene conflictos** (verificado: 0 conflictos en `LL1_GRAMMAR`; 20 en `ORIGINAL_GRAMMAR`).

| Regla G2 | Producción G2 | Gramática del código (`grammar.py`) | Función en el parser (`parser.py`) | Estado |
|---|---|---|---|---|
| R1 | `<programa> ::= TARGET NODE HEX_ADDR <bloque>` | `<programa> ::= <objetivo> <programa'>` (:59); `<programa'> ::= <objetivo> <programa'> \| ε` (:61-62); `<objetivo> ::= TARGET NODE HEX_ADDR <bloque>` (:64) | `_programa` :229-247; `_objetivo` :249-256 | **Difiere** (acepta 1 o más objetivos) |
| R2 | `<bloque> ::= { <lista_instr> }` | :66 | `_bloque` :258-262 | Cumple |
| R3 | `<lista_instr> ::= <instruccion> <lista_instr'>` | `<lista_sent> ::= <sentencia> <lista_sent'>` :68 | `_lista_sent` :264-267 | Cumple (otro nombre) |
| R4 | `<lista_instr'> ::= <instruccion> <lista_instr'>` | :70 | `_lista_sent` :270-273 | Cumple (otro nombre) |
| R5 | `<lista_instr'> ::= ε` | :71 | `_lista_sent` :274-277 | Cumple. También toma ε con EOF (:274), que no está en FOLLOW; el error lo reporta luego `expect('}')` |
| R6 | `<instruccion> ::= <secuencia> ;` | `<sentencia> ::= <secuencia> ;` :73 | `_sentencia` :285-287 | Cumple (otro nombre) |
| R7 | `<instruccion> ::= <condicional>` | :74 | `_sentencia` :288-289 | Cumple (otro nombre) |
| R8 | `<secuencia> ::= <accion> <secuencia'>` | :76 | `_secuencia` :295 | Cumple |
| R9 | `<secuencia'> ::= -> <accion> <secuencia'>` | :78 | `_secuencia` :298-302 | Cumple |
| R10 | `<secuencia'> ::= ε` | :79 | `_secuencia` :303-305 (solo con `;` = FOLLOW) | Cumple |
| R11 | `<accion> ::= SCAN PORTS` | `<accion> ::= SCAN <accion'>` :81; `<accion'> ::= PORTS` :90 | `_accion` :311-312; `_accion_p` :321-322 | **Difiere** (factorizada; el árbol tiene un nodo `<accion'>` de más) |
| — | *(no existe en G2)* | `<accion'> ::= PORT TK_NUM` :91 | `_accion_p` :323-324 | **Extra**: acepta `SCAN PORT 22` |
| R12 | `<accion> ::= CONNECT PORT NUM` | :82 | `_accion` :313-316 + `ACCIONES_SIMPLES` :49 | Cumple (`TK_NUM` en vez de `NUM`) |
| R13 | `BYPASS FIREWALL` | :83 | ídem + :50 | Cumple |
| R14 | `DISABLE FIREWALL` | :84 | ídem + :51 | Cumple |
| R15 | `INJECT PAYLOAD STRING` | :85 | ídem + :52 | Cumple |
| R16 | `EXECUTE SCRIPT STRING` | :86 | ídem + :53 | Cumple |
| R17 | `EXFIL DATA` | :87 | ídem + :54 | Cumple |
| R18 | `CLEAR LOGS` | :88 | ídem + :55 | Cumple |
| R19 | `<condicional> ::= IF <condicion> THEN <bloque> <resto_if>` | `... <condicional'>` :93 | `_condicional` :327-334 | Cumple (otro nombre) |
| R20 | `<resto_if> ::= ELSE <bloque>` | `<condicional'>` :95 | `_condicional_p` :338-340 | Cumple (otro nombre) |
| R21 | `<resto_if> ::= ε` | :96 | `_condicional_p` :341-342 (FOLLOW calculado) | Cumple (otro nombre) |
| R22 | `<condicion> ::= ICE_LEVEL <op_rel> NUM` | `ICE_LEVEL <comp> TK_NUM` :98 | `_condicion` :347-350 | Cumple (otros nombres) |
| R23 | `<condicion> ::= FIREWALL == <estado>` | :99 | `_condicion` :351-354 | Cumple |
| R24 | `<op_rel> ::= >` | `<comp> ::= >` :101 | `_comp` :357-362 | Cumple (otro nombre) |
| R25 | `<op_rel> ::= <` | :102 | `_comp` | Cumple (otro nombre) |
| R26 | `<op_rel> ::= ==` | :103 | `_comp` | Cumple (otro nombre) |
| R27 | `<estado> ::= ACTIVE` | :105 | `_estado` :364-369 | Cumple |
| R28 | `<estado> ::= INACTIVE` | :106 | `_estado` | Cumple |

**Resumen:** 25 Cumple (14 de ellas con otro nombre de no terminal o de terminal), 2 Difiere (R1, R11) y 1 producción extra. **Numeración:** el código numera por no terminal (1–16, con alternativas `10a`…`10h`; `grammar.py:134-141`) y no usa R1–R28.

### (b).3 Paso 6 — Casos de prueba

Archivos en `/tmp/netrunner_cp/cpNN.nr`. Para cada uno se ejecutó `python main.py cpNN.nr --cli`. Los casos con `{ … }` se completaron con `TARGET NODE 0xFF`, como en la Tabla 14 del PDF.

| Caso | Entrada | Esperado | Salida real | Exit | ¿Coincide? |
|---|---|---|---|---|---|
| CP-01 | `TARGET NODE 0xFF { SCAN PORTS; }` | Acepta | Árbol de 22 líneas (3 ε) | 0 | Sí |
| CP-02 | `… 0x1A2B { SCAN PORTS -> CONNECT PORT 8080 -> EXFIL DATA; }` | Acepta | Árbol de 33 líneas | 0 | Sí |
| CP-03 | `… 0xAD23D { IF ICE_LEVEL > 3 THEN {…} ELSE {…} CLEAR LOGS; }` | Acepta | Árbol de 61 líneas | 0 | Sí |
| CP-04 | IF anidado + `// fase de evasion` + `INJECT PAYLOAD "rootkit"` + `EXECUTE SCRIPT "escalar.sh"` | Acepta | Árbol de 66 líneas; el comentario se descarta | 0 | Sí |
| CP-05 | `{ SCAN PORTS }` | Sintáctico | `[Sintáctico] 1:31 Se esperaba ';' o '->', pero se encontró '}'` | 1 | Sí |
| CP-06 | `{ SCAN PORTS -> ; }` | Sintáctico | `[Sintáctico] 1:34 Se esperaba 'SCAN', 'CONNECT', 'BYPASS', 'DISABLE', 'INJECT', 'EXECUTE', 'EXFIL' o 'CLEAR', pero se encontró ';'` | 1 | Sí |
| CP-07 | `{ ELSE { CLEAR LOGS; } }` | Sintáctico | `1:20 Se esperaba una instrucción, pero se encontró 'ELSE'` **+ cascada** `1:41 Se esperaba 'TARGET' o fin de archivo, pero se encontró '}'` | 1 | Sí (2 errores) |
| CP-08 | `{ SCAN PORTS;` (sin `}`) | Sintáctico | `[Sintáctico] 2:1 Se esperaba una instrucción o '}', pero se encontró fin de archivo` | 1 | Sí |
| CP-09 | `{ }` | Sintáctico | `[Sintáctico] 1:20 Se esperaba una instrucción, pero se encontró '}'` | 1 | Sí |
| CP-10 | `TARGET NODE 255 {…}` | Sintáctico | `[Sintáctico] 1:13 Se esperaba una dirección hexadecimal, pero se encontró '255'` | 1 | Sí |
| CP-11 | `SCAN@PORTS` | Léxico | `[Léxico] 1:24 Símbolo '@' no pertenece al alfabeto de NetRunner` | 1 | Sí |
| CP-12 | `scan PORTS` | Léxico | `[Léxico] 1:20 Las palabras reservadas van en MAYÚSCULAS…` **+** `[Sintáctico] 1:25 Se esperaba una instrucción, pero se encontró 'PORTS' (posible consecuencia de un error léxico anterior)` | 1 | Sí (léxico + derivado) |
| CP-13 | `IF FIREWALL = ACTIVE THEN …` | Léxico | `[Léxico] 1:32 '=' solo…` **+** `[Sintáctico] 1:34 Se esperaba '=='…` **+** `[Sintáctico] 1:62 Se esperaba 'TARGET' o fin de archivo…` | 1 | Sí (1 léxico + 2 en cascada) |

**Casos adicionales** (para documentar los extras):

| Entrada | Resultado real | Según G2 |
|---|---|---|
| `TARGET NODE 0xFF { SCAN PORT 22; }` | **Aceptado** (exit 0) | Debería rechazarse (no hay regla) |
| `TARGET NODE 0x1 {…} TARGET NODE 0x2 {…}` | **Aceptado** (exit 0) | Debería rechazarse (R1 admite un solo objetivo) |
| `TARGET NODE 0x { … }` | Léxico 1:13 + Sintáctico 1:16 | Léxico ✔ |
| `INJECT PAYLOAD "abc; }` | Léxico 1:34 + Sintáctico 2:1 | Léxico ✔ |
| `SCAN PORTS - CLEAR LOGS;` | Léxico 1:30 + Sintáctico 1:32 | Léxico ✔ |
| `python main.py --cli` (sin archivo) / archivo inexistente | Mensaje claro, exit 2 | — |

**Pruebas del proyecto:** `python -m pytest` → `230 passed in 6.28s`. Entre ellas hay una verificación cruzada contra un parser LL(1) de pila guiado por la tabla (`tests/test_parser.py:307-401`): una evidencia fuerte de que el descenso recursivo corresponde a la tabla M **de la gramática del código**.

### Paso 4 — Árbol

- Se construye en cada método del parser (`Node`, `leaf`, `epsilon`: `tree.py:20`, `:66`, `:71`). **Si hubo cualquier error, el árbol es `None`** (`parser.py:183`), así que con errores no hay árbol parcial.
- Se imprime con `to_ascii` (`tree.py:146-163`) usando `├──`/`└──`. **Muestra los nodos primados y las hojas ε** (por ejemplo `<secuencia'>` → `ε`), como la Figura 5 y la §3.4 del PDF.
- Las hojas muestran `lexema [TIPO @línea:col]` (`tree.py:139-143`), por ejemplo `0xFF [HEX_ADDR @1:13]`. El PDF muestra solo el lexema.
- `--simplificar` (`tree.py:98-131`) quita ε y primados (forma E-BNF). `--dot` y `--svg` exportan el árbol (`tree.py:175`, `:225`).
- Diferencias con la §3.4 del PDF: la raíz tiene `<objetivo>` y `<programa'>` de más; `<lista_sent>`/`<sentencia>` reemplazan a `<lista_instr>`/`<instruccion>`; `SCAN PORTS` cuelga de `<accion'>`.

### Paso 5 — Errores

- **Léxicos:** se reportan todos en una sola pasada, con línea:columna y longitud para resaltar (`lexer.py:236-240`).
- **Sintácticos:** el mensaje es “Se esperaba {conjunto}, pero se encontró {token}”. El conjunto esperado se acumula con `check`/`expected` (`parser.py:139-148`) y, si contiene todo FIRST(sentencia), se resume como “una instrucción” (`parser.py:80-94`). Si el error viene después de un error léxico, se agrega “(posible consecuencia de un error léxico anterior)” (`parser.py:170-171`).
- **Recuperación en modo pánico: sí**, en tres niveles:
  - sentencia: descarta hasta `;`, `}`, FIRST(sentencia) o EOF (`parser.py:202-223`);
  - objetivo: hasta `TARGET` o EOF (`:189-200`);
  - tokens fuera de un objetivo (`:242-247`).
  Tope de 100 diagnósticos y nunca dos en la misma posición (`:31`, `:165`).
- **No se detiene en el primer error.** Efecto secundario: errores en cascada (CP-07, CP-13). El conjunto de sincronización difiere un poco del PDF (§3.5: `{ ;, } } ∪ SIGUIENTE(A)`): el código usa FIRST(sentencia) en lugar de SIGUIENTE(A).

---

## 7. Rúbrica: “hardcodeo” y código muerto

| Hallazgo | Archivo:línea | Gravedad |
|---|---|---|
| Ruta de entrada por argumento; no hay rutas absolutas | `main.py:51`, `:92-94` | ✔ |
| No hay `re` ni validaciones con regex en ninguna parte | — | ✔ |
| FIRST/FOLLOW **calculados** desde la gramática, no escritos a mano | `parser.py:33-45` | ✔ |
| `ACCIONES_SIMPLES` copia a mano las alternativas de `<accion>` | `parser.py:48-56` | Baja: es normal en descenso recursivo, pero duplica `grammar.py:82-88`. Si se cambia una, hay que cambiar la otra |
| Las alternativas de `_comp` y `_estado` están escritas como literales | `parser.py:359`, `:366` | Baja (mismo motivo) |
| ε en `<lista_sent'>` también con EOF (no está en FOLLOW) | `parser.py:274` | Baja: es un `if` que no sale de la tabla M; solo sirve para mejorar el mensaje |
| Lista fija de 7 ejemplos y ruta relativa al paquete | `examples.py:9-19` | Baja (solo la usa la GUI) |
| La GUI abre siempre `ok_1_completo.nr` si no recibe archivo | `gui/app.py:33`, `:65` | Baja, pero ese ejemplo **no es válido según G2** |
| `sys.setrecursionlimit(10000)` | `main.py:169` | Informativo (para IF muy anidados) |
| Etiqueta “Sintáctico” por defecto para cualquier `kind` desconocido | `main.py:72` | Informativo |
| **Código muerto en producción** (solo lo usan las pruebas): `initial_symbols` | `afd_tables.py:329` | Baja |
| ídem: `format_ll1_table` (la GUI usa su propia tabla) | `grammar.py:336` | Baja |
| ídem: `frontier` | `tree.py:88` | Baja |
| `subprocess` en pruebas, aunque AGENTS.md lo prohíbe | `tests/test_cli.py:3` | Baja (incumple una regla interna, no la rúbrica) |
| `.pyc` versionados, sin `.gitignore` | `netrunner/__pycache__/`, `netrunner/gui/__pycache__/` | Baja (aspecto del repositorio) |

---

## (c) Discrepancias documento ↔ código

| # | Discrepancia | Documento | Código | Recomendación |
|---|---|---|---|---|
| D1 | Varios objetivos por programa | R1: un solo `TARGET` | `<programa> ::= <objetivo> <programa'>` (`grammar.py:59-64`) | **Ajustar el código** (volver a R1) **o** agregar `<objetivo>`/`<programa'>` a G2. Como el PDF es lo entregado y R1 está demostrado en las Tablas 7–10, lo más barato y coherente es ajustar el código. Hay que actualizar `examples/ok_1_completo.nr` y las pruebas `test_objetivos_multiples` y `test_2000_objetivos` |
| D2 | `SCAN PORT NUM` | No existe; §2.6 dice que PORT/PORTS no generan conflicto | `<accion'> ::= PORT TK_NUM` (`grammar.py:91`) | Igual que D1: **ajustar el código** (quitar `<accion'>`, dejar `SCAN PORTS` como R11) o documentar la factorización en §2.6. Afecta a `ok_1_completo.nr` (líneas 4 y 23) y al README §8 |
| D3 | Nombres de no terminales | `<lista_instr>`, `<instruccion>`, `<resto_if>`, `<op_rel>` | `<lista_sent>`, `<sentencia>`, `<condicional'>`, `<comp>` | **Ajustar el código** (renombrar es mecánico) **o** el documento. Así el árbol impreso coincide con la Figura 5 |
| D4 | Nombre del terminal entero | `NUM` | `TK_NUM` (`tokens.py:49`, `grammar.py`) | Documento: aclarar en la Tabla 1 que `NUM` = token `TK_NUM` (o renombrar el terminal en `_TERMINALES`) |
| D5 | Numeración de reglas | R1–R28 | 1–16 con `a/b…` (`grammar.py:134-141`) | **Ajustar el código** si se quiere que la GUI muestre R1–R28 (cambiar `production_label`) o explicarlo en el documento |
| D6 | “Gramática original” | G0 (§2.2): secuencia ambigua, `<cuerpo>`, ELSE colgante | `ORIGINAL_GRAMMAR` (`grammar.py:34-55`) es otra: ya sin ambigüedad, con varios objetivos y `SCAN PORT` | **Ajustar el código** para que la pestaña Gramática muestre G0 o G1 tal como están en el PDF |
| D7 | Comando de ejecución | §3.7: `python main.py pruebas/cp01.nr` genera el árbol | Ese comando **abre la GUI**; para la consola hace falta `--cli` (`main.py:176-178`) | **Ajustar el documento** (agregar `--cli`) |
| D8 | Idioma de los docstrings | §3.3: “documentación en inglés como en el código del proyecto” | Todo está en español (lo exige AGENTS.md) | **Ajustar el documento** |
| D9 | Fragmento de código de §3.3 | `programa()`, `instruccion()`, `NetRunnerSyntaxError`, `ACTIONS`, `self.current`, `tok.kind` | Nombres reales en §(e) | **Ajustar el documento** con los nombres de §(e) |
| D10 | Mensajes de error (Tabla 13) | p. ej. “'scan' no es palabra reservada”, “Operador incompleto '='”, “Se esperaba ';' y se encontró '}'”, “ELSE sin IF…”, “Se esperaba HEX_ADDR y se encontró NUM” | Textos reales en §(b).3 | **Ajustar el documento** copiando la salida real |
| D11 | Sincronización del modo pánico | `{ ;, } } ∪ SIGUIENTE(A)` | `;`, `}`, FIRST(sentencia), EOF; y `TARGET` a nivel de objetivo (`parser.py:211-223`, `:197`) | **Ajustar el documento** |
| D12 | Lexema máximo frente a la frontera `[A-Za-z0-9_]` | §3.2: maximal munch | El candidato completo debe ser aceptado (`lexer.py:142-162`) | **Documentar** la regla en §3.2 (es una mejora) |
| D13 | Cadenas | “`"..."`”; fin de línea o de archivo = sin cerrar | Igual, y además una sola línea y sin escapes | Documentar |
| D14 | Árbol con errores | §3.1: “árbol **o** listado de errores” | Igual: `tree=None` si hay errores | Coinciden ✔ |
| D15 | Salida esperada de §3.4 | Hojas con solo el lexema | `lexema [TIPO @l:c]` | Documento (actualizar el ejemplo de salida) o código (`_texto_ascii`, `tree.py:139`) |

---

## (d) Extras (implementados pero no especificados)

| Extra | Dónde | ¿Contradice G2? |
|---|---|---|
| Varios `TARGET` por archivo (`<objetivo>`, `<programa'>`) | `grammar.py:59-64`, `parser.py:229-256` | **Sí**: amplía el lenguaje |
| Acción `SCAN PORT NUM` (`<accion'>`) | `grammar.py:81`, `:90-91`, `parser.py:319-325` | **Sí**: amplía el lenguaje |
| `ORIGINAL_GRAMMAR` distinta de G0/G1 | `grammar.py:34-55` | **Sí** (contradice §2.2–2.4) |
| Cálculo automático de FIRST, FOLLOW, tabla LL(1) y conflictos | `grammar.py:155-287` | No: refuerza el acoplamiento |
| Flags `--tokens`, `--simplificar`, `--dot`, `--svg` | `main.py:54-61` | No |
| Árbol simplificado (sin ε ni primados) | `tree.py:98-131` | No |
| Exportación DOT y SVG, layout del árbol | `tree.py:175-267`, `tree_layout.py` | No |
| GUI completa: editor con resaltado, análisis al escribir, pestañas Tokens/Árbol/Árbol gráfico/Errores/Gramática, exportar CSV/TXT/DOT/SVG | `netrunner/gui/*` | No |
| Traza del AFD por token (`q0 —0→ q1 …`) | `tokens.py:75`, `gui/panels.py:42` | No (útil en la sustentación) |
| Mensajes especiales: `/` solo, `.`, guiones y comillas tipográficas | `lexer.py:30-31`, `:118`, `:194-205` | No |
| Marca `after_lex_error` en los mensajes sintácticos | `lexer.py:223-231`, `parser.py:170-171` | No |
| Límite de 100 errores y deduplicación por posición | `parser.py:31`, `:165` | No |
| Códigos de salida 0/1/2 | `main.py:24-26` | No |
| DPI de Windows y UTF-8 forzado en la consola | `main.py:154-159`, `:170-174` | No |
| `ICE_LEVEL == NUM` | `grammar.py:103` | No (está en R26) |

---

## (e) Nombres reales para la sección 3 del documento

**Tabla 12 (no terminal → función):**

| No terminal G2 | Nombre en el código | Método real |
|---|---|---|
| `<programa>` | `<programa>` + `<objetivo>` + `<programa'>` | `Parser._programa` (`parser.py:229`), `Parser._objetivo` (`:249`) |
| `<bloque>` | `<bloque>` | `Parser._bloque` (`:258`) |
| `<lista_instr>` / `<lista_instr'>` | `<lista_sent>` / `<lista_sent'>` | `Parser._lista_sent` (`:264`) |
| `<instruccion>` | `<sentencia>` | `Parser._sentencia` (`:283`) |
| `<secuencia>` / `<secuencia'>` | igual | `Parser._secuencia` (`:292`) |
| `<accion>` | `<accion>` + `<accion'>` | `Parser._accion` (`:309`), `Parser._accion_p` (`:319`) |
| `<condicional>` / `<resto_if>` | `<condicional>` / `<condicional'>` | `Parser._condicional` (`:327`), `Parser._condicional_p` (`:336`) |
| `<condicion>` | igual | `Parser._condicion` (`:345`) |
| `<op_rel>` | `<comp>` | `Parser._comp` (`:357`) |
| `<estado>` | igual | `Parser._estado` (`:364`) |

**Otros nombres usados en el fragmento de §3.3 y en las Tablas 11 y 15:**

| En el documento | Nombre real |
|---|---|
| `class Parser` | `netrunner.parser.Parser` (`parser.py:104`); entrada `Parser(tokens).parse()` → `ParseResult(tree, errors)` (`:72`, `:180`) |
| `expect(kind)` | `Parser.expect(t)` (`:150`), con `check` (`:139`), `check_any` (`:146`), `advance` (`:131`), `fail` (`:156`), `report` (`:161`) |
| `self.current`, `tok.kind` | `Parser.tok` (`:124`), `Token.terminal` (`tokens.py:90`) |
| `NetRunnerSyntaxError` | `ParseError` (`parser.py:68`) + `Diagnostic` (`diagnostics.py:13`) |
| `ACTIONS` (= ACC) | `FIRST_SECUENCIA` (calculado, `parser.py:44`) y `ACCIONES_SIMPLES` (`:48`); `FIRST_SENTENCIA` (`:43`); `FOLLOW_CONDICIONAL_P` (`:45`) |
| Modo pánico | `_sentencia_segura` (`:202`), `_sincronizar_sentencia` (`:211`), `_objetivo_seguro` (`:189`) |
| `Node(kind, lexeme=…)`, `node.add` | `Node(symbol, children, token)` (`tree.py:20`), `leaf(token)` (`:71`), `epsilon()` (`:66`), `children.append` |
| Impresión jerárquica | `to_ascii` (`tree.py:146`); además `simplify` (`:98`), `to_dot` (`:175`), `to_svg` (`:225`) |
| Analizador léxico | `Lexer(source).tokenize()` → `LexResult(tokens, all_tokens, errors)` (`lexer.py:35`, `:49`, `:77`) |
| AFD / tablas | `KEYWORD_AFD`, `NUM_AFD`, `STR_AFD`, `OPS_AFD`, `WS_AFD`; `build_keyword_afd` (`afd_tables.py:177`); `run_afd` (`:240`); `AFDFamily` (`:293`) |
| Token | `Token(type, lexeme, line, col, trace, family, after_lex_error)` (`tokens.py:58`); `TokenType` (`:9`); `RESERVED_WORDS` (`:29`) |
| Gramática y tabla M | `LL1_GRAMMAR` (`grammar.py:57`), `compute_first` (`:178`), `compute_follow` (`:202`), `build_ll1_table` (`:260`), `find_conflicts` (`:281`) |
| Programa principal | `main.py`: `main` (`:167`), `ejecutar_cli` (`:87`), `construir_argumentos` (`:38`), `formatear_diagnostico` (`:70`) |
| Comando | `python main.py pruebas/cp01.nr --cli` |

---

## (f) Riesgos para la sustentación

1. **(Alto) “Muéstrenme la regla R22 en el código”.** Ni la numeración ni los nombres coinciden con G2, y la GUI muestra `14a` y `<comp>`. Si un evaluador compara la Figura 5 con el árbol impreso, verá `<objetivo>`, `<programa'>`, `<lista_sent>` y `<accion'>`, que no están en G2. Deben tener la tabla de §(b).2 a mano o alinear el código.
2. **(Alto) El lenguaje aceptado es más grande que L(G2).** `SCAN PORT 22` y varios `TARGET` se aceptan, pero según el documento deben rechazarse. El evaluador puede probarlo, y el ejemplo que abre la GUI (`ok_1_completo.nr`) usa ambas cosas. Esto pega directo en el criterio “acoplado a la gramática entregada”.
3. **(Medio) `python main.py archivo.nr` abre la GUI**, aunque el PDF (§3.7) dice que imprime el árbol. Hay que recordar `--cli`.
4. **(Medio) Errores en cascada.** En CP-07 y CP-13 hay 2 o 3 errores donde el documento sugiere uno. Conviene saber explicarlo como un efecto normal del modo pánico (README §10.17).
5. **(Medio) Modificación en vivo (§4.2, `WHILE`).** En el código hay que tocar: `RESERVED_WORDS` (`tokens.py:29`; el trie se regenera solo), `LL1_GRAMMAR` (`grammar.py:73-74`), un método `_bucle` nuevo y una rama en `_sentencia` (`parser.py:283-290`). FIRST/FOLLOW se recalculan solos. **Ojo: varias pruebas fallarán por conteos fijos**: `tests/test_afd_tables.py:26` (111 estados), `:30` y `tests/test_lexer.py:16-17` (23 palabras), `tests/test_grammar.py:99-100` (16 no terminales, 33 alternativas). Ensáyenlo antes.
6. **(Medio) El documento dice que los docstrings están en inglés** y el fragmento de §3.3 no existe tal cual en el código. Si se pide “muéstrenme `instruccion()`”, la función se llama `_sentencia`.
7. **(Bajo) Tamaño del proyecto.** Son unas 5 200 líneas, ~1 565 de ellas de GUI. Cada integrante debe poder explicar `run_afd`, `_leer_candidato`, `compute_first`/`compute_follow` y el mecanismo `expected`, porque son la parte “de la materia”.
8. **(Bajo) Frontera del lexema.** Si preguntan por maximal munch con `22abc`, el código no da `NUM` + error sino un único error; hay que justificarlo.
9. **(Bajo) Consola de Windows.** Usar el núcleo fuera de `main.py` (por ejemplo, imprimir `format_first_follow()` directamente) falla con `UnicodeEncodeError` por la `ε` en cp1252. `main.py` lo evita forzando UTF-8.
10. **(Bajo) Repositorio.** Hay `.pyc` versionados y falta `.gitignore`; el PDF de `docs/` no está en git.

---

## (g) Cambios aplicados después de la auditoría (2026-11-11)

El código se alineó con el documento. `python -m pytest` → **232 passed**; CP-01…CP-13 siguen dando el resultado esperado, ahora con `python main.py cpNN.nr` (sin `--cli`).

| Discrepancia | Estado | Cambio |
|---|---|---|
| D1 varios `TARGET` | Corregida | Se eliminaron `<objetivo>`/`<programa'>`; R1 exacta. Texto después del `}` final → “Se esperaba fin de archivo…” (`parser.py`, `_programa`) |
| D2 `SCAN PORT NUM` | Corregida | Se eliminó `<accion'>`; R11 = `SCAN PORTS` |
| D3 nombres | Corregida | `<lista_instr>`, `<instruccion>`, `<resto_if>`, `<op_rel>`; métodos `_lista_instr`, `_instruccion`, `_resto_if`, `_op_rel` |
| D4 `NUM` | Corregida | El terminal de `TK_NUM` es `NUM` (`tokens.py`) |
| D5 numeración | Corregida | `production_label` devuelve `R1`…`R28`; `LL1_GRAMMAR` está en el orden de la Tabla 6 |
| D6 gramática original | Corregida | `ORIGINAL_GRAMMAR` = G1 (§2.4) |
| D7 comando | Corregida | `python main.py archivo.nr` analiza en consola; GUI con `python main.py` o `--gui` |
| Duplicación `ACCIONES_SIMPLES` | Corregida | `ACCIONES` se construye desde `LL1_GRAMMAR` |
| D8–D13, D15 | Pendientes en el documento | Solo se pueden corregir en el PDF (idioma, fragmento §3.3, mensajes de la Tabla 13, sincronización, frontera del lexema, formato de las hojas) |

Nombres reales actualizados para la Tabla 12: `_programa`, `_bloque`, `_lista_instr`, `_instruccion`, `_secuencia`, `_accion`, `_condicional`, `_resto_if`, `_condicion`, `_op_rel`, `_estado` (todos en `netrunner/parser.py`), y `ACCIONES`, `FIRST_INSTRUCCION`, `FOLLOW_RESTO_IF`.
