"""Ponto de entrada da interface do NaveHub.

Prioriza a GUI PySide6 e preserva o Tkinter como fallback para rollback.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QToolButton

from .main_window import MainWindow as TkMainWindow


def get_main_window_class():
    try:
        from .pyside_main_window import MainWindow as QtMainWindow
    except Exception:
        return TkMainWindow

    class NaveHubQtMainWindow(QtMainWindow):
        """Ajustes visuais da navegação sem alterar a lógica da janela principal."""

        def _build_app_shell(self, selected_platform=None):
            body, body_layout = super()._build_app_shell(selected_platform)

            # A barra superior passa a ser uma extensão do background principal,
            # eliminando o bloco escuro que envolvia a navegação.
            if self.topbar is not None:
                self.topbar.setStyleSheet(
                    "background: #070A0D; border-bottom: 1px solid transparent;"
                )

                for button in self.topbar.findChildren(QToolButton):
                    if button.property("role") != "platform-tab":
                        continue

                    # Logos maiores, sem caixa escura e com área de clique confortável.
                    button.setFixedSize(180, 64)
                    button.setIconSize(QSize(158, 52))

                    active = button.property("active") is True
                    if active:
                        button.setStyleSheet(
                            "QToolButton {"
                            "background: transparent;"
                            "border: 0;"
                            "border-bottom: 2px solid #2BB39A;"
                            "border-radius: 0;"
                            "padding: 0;"
                            "}"
                            "QToolButton:hover {"
                            "background: rgba(43, 179, 154, 0.08);"
                            "}"
                        )
                    else:
                        button.setStyleSheet(
                            "QToolButton {"
                            "background: transparent;"
                            "border: 0;"
                            "border-radius: 0;"
                            "padding: 0;"
                            "}"
                            "QToolButton:hover {"
                            "background: rgba(234, 242, 243, 0.05);"
                            "}"
                        )

            return body, body_layout

    return NaveHubQtMainWindow


def create_main_window(config):
    return get_main_window_class()(config)
