"""Configuración de pytest.

Este archivo, en la raíz del proyecto, hace que pytest agregue la raíz a
sys.path. Así ``pytest`` encuentra el paquete ``netrunner`` aunque se ejecute
desde otra carpeta o mediante el comando ``pytest`` (y no ``python -m pytest``).
"""
