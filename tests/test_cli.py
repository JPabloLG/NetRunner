"""Pruebas del modo consola de main.py (ejecutado con subprocess)."""

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from netrunner.examples import EXAMPLES_DIR

RAIZ = Path(__file__).resolve().parent.parent
MAIN = RAIZ / "main.py"

VALIDO = (
    "TARGET NODE 0xad23d {\n"
    "    SCAN PORTS -> EXFIL DATA;\n"
    "    IF FIREWALL == ACTIVE THEN { BYPASS FIREWALL; }\n"
    "}\n"
)
MIXTO = (
    "TARGET NODE 0x1 {\n"
    "    SCAN PORTS @;\n"   # léxico
    "    CONNECT 22;\n"     # sintáctico
    "}\n"
)


def correr(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(MAIN), *args],
        capture_output=True, text=True, encoding="utf-8", cwd=RAIZ, timeout=60,
    )


@pytest.fixture
def valido(tmp_path: Path) -> Path:
    ruta = tmp_path / "valido.nr"
    ruta.write_text(VALIDO, encoding="utf-8")
    return ruta


@pytest.fixture
def mixto(tmp_path: Path) -> Path:
    ruta = tmp_path / "mixto.nr"
    ruta.write_text(MIXTO, encoding="utf-8")
    return ruta


def test_archivo_valido(valido: Path) -> None:
    r = correr(str(valido), "--cli")
    assert r.returncode == 0, r.stderr
    assert "<programa>" in r.stdout
    assert "<programa'>" in r.stdout
    assert "SCAN [TK_CMD @2:5]" in r.stdout


def test_errores_mixtos(mixto: Path) -> None:
    r = correr(str(mixto), "--cli")
    assert r.returncode == 1
    lineas = [l for l in r.stdout.splitlines() if l.startswith("[")]
    assert lineas == [
        "[Léxico] 2:16  Símbolo '@' no pertenece al alfabeto de NetRunner",
        "[Sintáctico] 3:13  Se esperaba 'PORT', pero se encontró '22'",
    ]
    assert "<programa>" not in r.stdout


def test_archivo_inexistente(tmp_path: Path) -> None:
    r = correr(str(tmp_path / "no_existe.nr"), "--cli")
    assert r.returncode == 2
    assert "no existe" in r.stderr


def test_tokens(valido: Path) -> None:
    r = correr(str(valido), "--cli", "--tokens")
    assert r.returncode == 0
    assert "Tipo" in r.stdout and "Lexema" in r.stdout
    assert "HEX_ADDR" in r.stdout and "0xad23d" in r.stdout
    assert "EOF" in r.stdout


def test_tokens_con_errores(mixto: Path) -> None:
    r = correr(str(mixto), "--cli", "--tokens")
    assert r.returncode == 1
    assert "TK_CMD" in r.stdout


def test_simplificar(valido: Path) -> None:
    r = correr(str(valido), "--cli", "--simplificar")
    assert r.returncode == 0
    assert "<programa>" in r.stdout
    assert "'>" not in r.stdout  # sin auxiliares
    assert "ε" not in r.stdout


def test_exportar_dot_y_svg(valido: Path, tmp_path: Path) -> None:
    dot, svg = tmp_path / "arbol.dot", tmp_path / "arbol.svg"
    r = correr(str(valido), "--cli", "--dot", str(dot), "--svg", str(svg))
    assert r.returncode == 0
    assert dot.read_text(encoding="utf-8").startswith("digraph arbol {")
    ET.fromstring(svg.read_text(encoding="utf-8"))


def test_exportar_simplificado(valido: Path, tmp_path: Path) -> None:
    dot = tmp_path / "s.dot"
    correr(str(valido), "--cli", "--simplificar", "--dot", str(dot))
    assert "<programa'>" not in dot.read_text(encoding="utf-8")


def test_no_exporta_con_errores(mixto: Path, tmp_path: Path) -> None:
    dot = tmp_path / "x.dot"
    r = correr(str(mixto), "--cli", "--dot", str(dot))
    assert r.returncode == 1
    assert not dot.exists()


def test_cli_sin_tkinter(valido: Path) -> None:
    """Con Tkinter bloqueado, el modo consola debe funcionar igual."""
    codigo = (
        "import sys; sys.modules['tkinter'] = None\n"
        "import main\n"
        f"codigo = main.main([{str(valido)!r}, '--cli'])\n"
        "assert 'netrunner.gui.app' not in sys.modules\n"
        "sys.exit(codigo)\n"
    )
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True,
                       text=True, encoding="utf-8", cwd=RAIZ, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "<programa>" in r.stdout


def test_gui_sin_tkinter_muestra_ayuda() -> None:
    codigo = (
        "import sys; sys.modules['tkinter'] = None\n"
        "import main\n"
        "sys.exit(main.main([]))\n"
    )
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True,
                       text=True, encoding="utf-8", cwd=RAIZ, timeout=60)
    assert r.returncode == 1
    assert "sudo apt install python3-tk" in r.stderr
    assert "--cli" in r.stderr


# --- Ejemplos oficiales (se omiten mientras estén vacíos) ------------------------


def _ejemplo(nombre: str) -> Path:
    ruta = EXAMPLES_DIR / nombre
    if not ruta.read_text(encoding="utf-8").strip():
        pytest.skip(f"{nombre} está vacío: falta el contenido oficial del ejemplo")
    return ruta


def test_ejemplo_valido_oficial() -> None:
    r = correr(str(_ejemplo("ok_1_completo.nr")), "--cli")
    assert r.returncode == 0
    assert "<programa>" in r.stdout


def test_error_1_mixto_oficial() -> None:
    r = correr(str(_ejemplo("error_1_mixto.nr")), "--cli")
    assert r.returncode == 1
    assert "[Léxico]" in r.stdout and "[Sintáctico]" in r.stdout
