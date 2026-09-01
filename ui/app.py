"""Ponto de entrada da interface do NaveHub.

Prioriza a GUI PySide6 e preserva o Tkinter como fallback para rollback.
"""

from __future__ import annotations

from .main_window import MainWindow as TkMainWindow


def get_main_window_class():
    try:
        from .pyside_main_window import MainWindow as QtMainWindow
    except Exception:
        return TkMainWindow
    return QtMainWindow


def create_main_window(config):
    return get_main_window_class()(config)
