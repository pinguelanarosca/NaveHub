from __future__ import annotations

import io
import json
import os
import shutil
import tarfile
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt, QTimer, QObject, Signal
from PySide6.QtGui import QAction, QCursor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from launcher.profile_launcher import STATIC_PLATFORM, ProfileLauncher

from .main_window import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_TEXT,
    ACCOUNT_ICON,
    BG,
    BG_BTN,
    BG_HOVER,
    BORDER,
    CARD_HOVER,
    COLS,
    DANGER,
    DANGER_HOVER,
    FG,
    FG_MUTED,
    PLATFORM_COLUMNS,
    PLATFORM_ICON,
    PLATFORMS,
    SURFACE,
    SURFACE_ELEVATED,
    WARNING,
)

APP_DESKTOP_ID = "navehub"
APP_DISPLAY_NAME = "NaveHub"

# Paleta escura exclusiva desta janela; não altera as constantes nem a lógica do launcher.

QT_STYLE = f"""
QMainWindow, QWidget {{
    background: {BG};
    color: {FG};
    font-family: "Avenir Next", "Segoe UI", Arial;
}}
QPushButton {{
    background: {BG_BTN};
    color: {FG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {BG_HOVER};
    border-color: {ACCENT};
}}
QPushButton[variant="primary"] {{
    background: {ACCENT};
    color: {ACCENT_TEXT};
    border-color: {ACCENT};
}}
QPushButton[variant="primary"]:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton[variant="danger"] {{
    background: {DANGER};
    color: {FG};
}}
QPushButton[variant="danger"]:hover {{
    background: {DANGER_HOVER};
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    color: {FG_MUTED};
    border-color: transparent;
}}
QPushButton[variant="warning"] {{
    background: transparent;
    color: {WARNING};
}}
QToolButton {{
    background: transparent;
    color: {FG_MUTED};
    border: 0;
    padding: 0;
}}
QToolButton:hover {{
    color: {FG};
}}
QToolButton[role="platform"] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 0px;
    padding: 0px;
}}
QToolButton[role="platform-tab"] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 3px 8px;
}}
QToolButton[role="platform-tab"]:hover {{
    background: {CARD_HOVER};
    border-color: {BORDER};
}}
QToolButton[role="platform-tab"][active="true"] {{
    background: {SURFACE_ELEVATED};
    border-color: {ACCENT};
}}
QToolButton[role="sidebar"] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    color: {FG_MUTED};
    font-size: 11px;
    font-weight: 700;
    padding: 0;
}}
QToolButton[role="sidebar"]:hover {{
    background: {CARD_HOVER};
    color: {FG};
}}
QFrame[role="sidebar"] {{
    background: {SURFACE};
    border-right: 1px solid {BORDER};
}}
QFrame[role="topbar"] {{
    /* alterado: caixa escura removida — a barra agora se mistura ao fundo da janela */
    background: transparent;
    border-bottom: none;
}}
QToolButton[role="platform"]:hover {{
    background: {CARD_HOVER};
    border-color: {CARD_HOVER};
}}
QToolButton[role="account"] {{
    background: {SURFACE};
    border: 1px solid transparent;
    border-radius: 12px;
    color: {FG_MUTED};
    padding: 5px 4px 4px;
    font-size: 9px;
    font-weight: 600;
}}
QToolButton[role="account"]:hover {{
    background: {CARD_HOVER};
    border-color: {BORDER};
    color: {FG};
}}
QToolButton[role="account"][status="A"] {{
    border-color: {ACCENT};
}}
QToolButton[role="account"][status="B"] {{
    border-color: {BORDER};
}}
QLineEdit {{
    background: {BG};
    color: {FG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
}}
QDialog, QMessageBox {{
    background: {SURFACE};
    color: {FG};
}}
QMenu {{
    background: {SURFACE_ELEVATED};
    color: {FG};
    border: 1px solid {BORDER};
}}
QMenu::item:selected {{
    background: {ACCENT};
    color: {ACCENT_TEXT};
}}
QLabel[role="brand"] {{
    color: {FG};
    font-size: 22px;
    font-weight: 800;
    letter-spacing: 1px;
}}
QLabel[role="section"] {{
    color: {FG_MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
}}
"""


class _FaviconSignals(QObject):
    progress = Signal(int)
    complete = Signal(dict)



class FadeIn(QWidget):
    """Small, non-blocking entrance transition for rebuilt views."""

    def showEvent(self, event):
        super().showEvent(event)
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(180)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.finished.connect(lambda: self.setGraphicsEffect(None))
        self._fade_animation = animation
        animation.start()


class VisualTile(QToolButton):
    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        self.setProperty("role", role)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMouseTracking(True)


ACCOUNT_TILE_WIDTH = 96
ACCOUNT_TILE_HEIGHT = 104
LEGALIZED_ACCOUNT_TILE_HEIGHT = 132
ACCOUNT_CARD_ICON = (68, 68)
HOME_CARD_WIDTH = 286
HOME_CARD_HEIGHT = 74
HOME_CARD_GAP = 6
SIDEBAR_WIDTH = 82
# alterado: tile da plataforma +30% (151x53 -> 196x69) para caber o ícone maior sem cortar
PLATFORM_TAB_WIDTH = 196
PLATFORM_TAB_HEIGHT = 69
GRID_HORIZONTAL_SPACING = 14
GRID_VERTICAL_SPACING = 14


class AccountButton(QToolButton):
    def __init__(self, profile_name: str, main_window: MainWindow):
        super().__init__()
        self.profile_name = profile_name
        self.main_window = main_window
        self._press_pos: QPoint | None = None
        self._dragged = False
        self._original_order: list[str] | None = None
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos: QPoint):
        menu = self.main_window.context_menu(self.profile_name)
        menu.exec(self.mapToGlobal(pos))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._dragged = False
            self._original_order = self.main_window._profile_order[:]
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_pos is not None:
            current = event.globalPosition().toPoint()
            distance = abs(current.x() - self._press_pos.x()) + abs(current.y() - self._press_pos.y())
            if distance >= 8:
                self._dragged = True
                self.main_window.move_profile_to_pointer(self.profile_name, current)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragged:
            if self._original_order != self.main_window._profile_order:
                self.main_window.launcher.save_profile_order(
                    self.main_window.current_platform,
                    self.main_window._profile_order,
                )
            self._press_pos = None
            self._original_order = None
            self._dragged = False
            return
        self._press_pos = None
        self._original_order = None
        super().mouseReleaseEvent(event)


class MainWindow:
    def __init__(self, config):
        self.config = config
        self.launcher = ProfileLauncher(config)
        self.current_platform = None
        self.image_cache = {}
        self._profile_order = []
        self._account_items = {}
        self._legalized_timer_editors = {}
        self._laying_out_profiles = False
        self._natural_grid_columns = COLS
        self.topbar = None
        self.platform_toolbar = None
        self.platform_actions = None
        self.profiles_scroll = None
        self._backup_thread = None
        self._backup_error = None
        self._backup_target = None
        self._restore_thread = None
        self._restore_error = None
        self._restore_source = None
        self._restore_total = 0
        self._restore_done = 0
        self._favicon_progress_total = 0
        self._favicon_progress_done = 0
        self._favicon_progress_running = False
        self._favicon_signals = _FaviconSignals()
        self._favicon_signals.progress.connect(
            self._update_favicon_progress
        )
        self._favicon_signals.complete.connect(
            self._finish_static_favicon_update
        )
        self._favicon_progress_running = False

        base = Path(__file__).parent.parent
        self.icons_platforms = base / "icons" / "platforms"
        self.icons_accounts = base / "icons" / "accounts"
        self.icons_platforms.mkdir(parents=True, exist_ok=True)
        self.icons_accounts.mkdir(parents=True, exist_ok=True)

        self.app = QApplication.instance() or QApplication([APP_DISPLAY_NAME])
        self.app.setApplicationName(APP_DISPLAY_NAME)
        self.app.setApplicationDisplayName(APP_DISPLAY_NAME)
        self.app.setDesktopFileName(APP_DESKTOP_ID)
        self.window = QMainWindow()
        self.window.setWindowTitle(APP_DISPLAY_NAME)
        self.window.setObjectName(APP_DISPLAY_NAME)
        self.window.setStyleSheet(QT_STYLE)
        self.window.setMinimumSize(700, 500)
        self.window.setSizeIncrement(1, 1)
        self.window.resizeEvent = self._window_resize_event

        icon = base / "icons" / "navehub" / "icondocnavegunb.png"
        if icon.exists():
            app_icon = QIcon(str(icon))
            self.app.setWindowIcon(app_icon)
            self.window.setWindowIcon(app_icon)

        self.main_frame = QWidget()
        self.window.setCentralWidget(self.main_frame)
        self.main_layout = QVBoxLayout(self.main_frame)

        self._countdown_timer = QTimer(self.window)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(
            self._refresh_legalized_timers
        )
        self._countdown_timer.start()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.center_account_windows()
        self.show_platform_menu()

    def _window_resize_event(self, event):
        QMainWindow.resizeEvent(self.window, event)
        if self.current_platform and hasattr(self, "grid"):
            QTimer.singleShot(0, self._relayout_profiles)

    def run(self):
        self.window.show()
        self.app.exec()

    def clear_frame(self):
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def fit_window_to_content(self):
        self.window.setMinimumSize(700, 500)
        if self.window.isMaximized():
            return
        screen = self.window.screen().availableGeometry()
        if self.current_platform is None:
            width = min(max(900, self.window.width()), screen.width() - 48)
            height = min(max(560, self.window.height()), screen.height() - 96)
            self.window.resize(width, height)
            return
        if self.current_platform and getattr(self, "_profile_order", None):
            columns = max(1, min(9, PLATFORM_COLUMNS.get(self.current_platform, COLS), len(self._profile_order)))
            rows = (len(self._profile_order) + columns - 1) // columns
            horizontal_spacing = self.grid.horizontalSpacing() if hasattr(self, "grid") else HOME_CARD_GAP
            vertical_spacing = self.grid.verticalSpacing() if hasattr(self, "grid") else HOME_CARD_GAP
            grid_width = columns * ACCOUNT_TILE_WIDTH + (columns - 1) * horizontal_spacing
            tile_height = (
                LEGALIZED_ACCOUNT_TILE_HEIGHT
                if self.current_platform == STATIC_PLATFORM
                else ACCOUNT_TILE_HEIGHT
            )
            grid_height = rows * tile_height + (rows - 1) * vertical_spacing
            topbar_height = self.topbar.sizeHint().height() if self.topbar else 0
            toolbar_height = self.platform_toolbar.sizeHint().height() if self.platform_toolbar else 0
            actions_height = self.platform_actions.sizeHint().height() if self.platform_actions else 0
            visible_grid_height = grid_height
            width = min(max(700, grid_width + SIDEBAR_WIDTH + 48), screen.width() - 48)
            height = max(500, visible_grid_height + topbar_height + toolbar_height + actions_height + 64)
            self.window.resize(width, height)
            return
        self.window.adjustSize()
        hint = self.window.sizeHint()
        width = min(max(hint.width(), 700), screen.width() - 48)
        height = min(max(hint.height(), 500), screen.height() - 96)
        self.window.resize(width, height)

    def set_window_geometry(self, width: int, height: int, *, centered=False):
        self.window.resize(width, height)
        if centered:
            screen = self.window.screen().availableGeometry()
            x = max(0, screen.x() + (screen.width() - width) // 2)
            y = max(0, screen.y() + (screen.height() - height) // 2)
            self.window.move(x, y)

    def btn(self, parent, text, command, *, variant="secondary"):
        button = QPushButton(text, parent)
        button.setProperty("variant", variant)
        button.clicked.connect(command)
        return button

    def show_dialog(self, title: str, message: str, *, kind="info", buttons=(("OK", True, "primary"),), width=430):
        box = QMessageBox(self.window)
        box.setWindowTitle(title)
        box.setText(message)
        box.setMinimumWidth(width)
        icons = {
            "info": QMessageBox.Information,
            "warning": QMessageBox.Warning,
            "error": QMessageBox.Critical,
        }
        box.setIcon(icons.get(kind, QMessageBox.Information))
        results = {}
        for label, value, _variant in buttons:
            role = QMessageBox.AcceptRole if value else QMessageBox.RejectRole
            results[box.addButton(label, role)] = value
        box.exec()
        return results.get(box.clickedButton())

    def show_info(self, title: str, message: str):
        self.show_dialog(title, message, kind="info")

    def show_error(self, title: str, message: str):
        self.show_dialog(title, message, kind="error")

    def show_warning(self, title: str, message: str):
        self.show_dialog(title, message, kind="warning")

    def ask_yes_no(self, title: str, message: str) -> bool:
        return bool(
            self.show_dialog(
                title,
                message,
                kind="warning",
                buttons=(("Não", False, "ghost"), ("Sim", True, "danger")),
                width=500,
            )
        )

    def center_account_windows(self):
        width, height = self.launcher.get_window_size()
        screen = self.window.screen().availableGeometry()
        x = max(0, screen.x() + (screen.width() - width) // 2)
        y = max(0, screen.y() + (screen.height() - height) // 2)
        self.launcher.set_window_position(x, y)

    def get_image(self, path: Path, size: tuple[int, int]):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = None
        key = (str(path), size, mtime)
        if key in self.image_cache:
            return self.image_cache[key]
        try:
            with Image.open(path) as src:
                frames = []
                for index in range(getattr(src, "n_frames", 1)):
                    src.seek(index)
                    frames.append(src.convert("RGBA"))
            img = max(frames, key=lambda frame: frame.size[0] * frame.size[1])
            img = img.resize(size, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            pixmap = QPixmap.fromImage(QImage.fromData(buffer.getvalue(), "PNG"))
            self.image_cache[key] = pixmap
            return pixmap
        except Exception as error:
            print(f"Erro ao carregar {path}: {error}")
            return None

    def icon_path(self, kind: str, platform: str, status: str) -> Path:
        if platform == STATIC_PLATFORM:
            folder = self.icons_platforms if kind == "platforms" else self.icons_accounts
            return folder / "outras.png"

        safe = platform.lower().replace(" ", "")
        folder = self.icons_platforms if kind == "platforms" else self.icons_accounts
        ext = "png" if status == "A" else "webp"
        return folder / f"{safe}_{status.lower()}.{ext}"

    def account_icon_path(self, platform: str, profile_name: str, status: str) -> Path:
        saved = self.launcher.get_profile_icon_path(platform, profile_name)
        if saved is not None:
            return saved
        if platform == STATIC_PLATFORM:
            profile_dir = self.launcher.get_profile_dir(platform, profile_name)
            matches = [
                path
                for path in profile_dir.glob("navehub_favicon*")
                if path.is_file() and not path.name.startswith(".")
            ]
            if matches:
                return sorted(matches)[0]
        return self.icon_path("accounts", platform, status)

    def grid_columns(self) -> int:
        if not hasattr(self, "profiles_frame"):
            return min(9, PLATFORM_COLUMNS.get(self.current_platform, COLS))
        max_columns = min(9, PLATFORM_COLUMNS.get(self.current_platform, COLS))
        if self._laying_out_profiles:
            return self._natural_grid_columns
        available = max(
            self.window.width() - SIDEBAR_WIDTH - 32,
            ACCOUNT_TILE_WIDTH,
        )
        spacing = self.grid.horizontalSpacing() if hasattr(self, "grid") else GRID_HORIZONTAL_SPACING
        return max(1, min(max_columns, (available + spacing) // (ACCOUNT_TILE_WIDTH + spacing)))

    def context_menu(self, profile_name: str) -> QMenu:
        menu = QMenu(self.window)
        actions = [
            ("Editar", lambda: self.edit_profile(profile_name)),
            ("Clonar", lambda: self.clone_profile(profile_name)),
            ("Limpeza pesada", lambda: self.heavy_clean_profile(profile_name)),
            ("Excluir", lambda: self.delete_profile(profile_name)),
        ]
        for label, command in actions:
            action = QAction(label, menu)
            action.triggered.connect(command)
            menu.addAction(action)
        return menu

    def _animate_view(self, widget: QWidget):
        widget.setObjectName("view")
        return widget

    def _section_label(self, text: str):
        label = QLabel(text)
        label.setProperty("role", "section")
        return label

    def _build_app_shell(self, selected_platform: str | None = None):
        """Build the shared navigation frame while leaving action wiring intact."""
        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setProperty("role", "sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 10, 8, 10)
        sidebar_layout.setSpacing(8)

        home = VisualTile("sidebar")
        home.setText("N")
        home.setToolButtonStyle(Qt.ToolButtonTextOnly)
        # Mantém o card no mesmo tamanho e aumenta somente o caractere.
        home.setFixedSize(66, 38)
        home.setStyleSheet(
            "QToolButton {"
            "font-size: 36px;"
            "font-weight: 900;"
            "padding: 0px;"
            "}"
        )
        home.setToolTip("Plataformas")
        home.clicked.connect(self.show_platform_menu)
        sidebar_layout.addWidget(home, alignment=Qt.AlignHCenter)
        sidebar_layout.addStretch(1)

        self.backup_progress_widget = QWidget()
        progress_layout = QVBoxLayout(
            self.backup_progress_widget
        )
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(2)

        self.backup_progress_label = QLabel("Backup 0%")
        self.backup_progress_label.setAlignment(
            Qt.AlignCenter
        )
        self.backup_progress_label.setStyleSheet(
            f"color: {FG_MUTED}; font-size: 8px; font-weight: 700;"
        )

        self.backup_progress_bar = QProgressBar()
        self.backup_progress_bar.setRange(0, 100)
        self.backup_progress_bar.setValue(0)
        self.backup_progress_bar.setTextVisible(False)
        self.backup_progress_bar.setFixedSize(66, 8)
        self.backup_progress_bar.setStyleSheet(
            f"""
QProgressBar {{
    background: {BG_BTN};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}
"""
        )

        progress_layout.addWidget(
            self.backup_progress_label
        )
        progress_layout.addWidget(
            self.backup_progress_bar
        )

        backup_running = (
            self._backup_thread is not None
            and self._backup_thread.is_alive()
        )

        self.backup_progress_widget.setVisible(
            backup_running
        )

        if backup_running:
            value = self._current_backup_percent()
            self.backup_progress_bar.setValue(value)
            self.backup_progress_label.setText(
                f"Backup {value}%"
            )

        sidebar_layout.addWidget(
            self.backup_progress_widget,
            alignment=Qt.AlignHCenter,
        )

        self.restore_progress_widget = QWidget()

        restore_progress_layout = QVBoxLayout(
            self.restore_progress_widget
        )
        restore_progress_layout.setContentsMargins(0, 0, 0, 0)
        restore_progress_layout.setSpacing(2)

        self.restore_progress_label = QLabel("Restaurar 0%")
        self.restore_progress_label.setAlignment(
            Qt.AlignCenter
        )
        self.restore_progress_label.setStyleSheet(
            f"color: {FG_MUTED}; font-size: 8px; font-weight: 700;"
        )

        self.restore_progress_bar = QProgressBar()
        self.restore_progress_bar.setRange(0, 100)
        self.restore_progress_bar.setValue(0)
        self.restore_progress_bar.setTextVisible(False)
        self.restore_progress_bar.setFixedSize(66, 8)
        self.restore_progress_bar.setStyleSheet(
            f"QProgressBar {{"
            f"background: {BG_BTN};"
            f"border: 1px solid {BORDER};"
            f"border-radius: 4px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"background: {WARNING};"
            f"border-radius: 3px;"
            f"}}"
        )

        restore_progress_layout.addWidget(
            self.restore_progress_label
        )
        restore_progress_layout.addWidget(
            self.restore_progress_bar
        )

        restore_running = (
            self._restore_thread is not None
            and self._restore_thread.is_alive()
        )

        self.restore_progress_widget.setVisible(
            restore_running
        )

        if restore_running:
            total = max(
                1,
                self._restore_total,
            )
            done = min(
                self._restore_done,
                total,
            )
            value = int(
                done * 100 / total
            )

            self.restore_progress_bar.setValue(
                value
            )
            self.restore_progress_label.setText(
                f"Restaurar {value}%"
            )

        sidebar_layout.addWidget(
            self.restore_progress_widget,
            alignment=Qt.AlignHCenter,
        )

        self.favicon_progress_widget = QWidget()
        favicon_layout = QVBoxLayout(
            self.favicon_progress_widget
        )
        favicon_layout.setContentsMargins(0, 0, 0, 0)
        favicon_layout.setSpacing(2)

        self.favicon_progress_label = QLabel("Favicons 0%")
        self.favicon_progress_label.setAlignment(Qt.AlignCenter)
        self.favicon_progress_label.setStyleSheet(
            f"color: {FG_MUTED}; font-size: 8px; font-weight: 700;"
        )

        self.favicon_progress_bar = QProgressBar()
        self.favicon_progress_bar.setRange(0, 100)
        self.favicon_progress_bar.setValue(0)
        self.favicon_progress_bar.setTextVisible(False)
        self.favicon_progress_bar.setFixedSize(66, 8)
        self.favicon_progress_bar.setStyleSheet(
            f"""
QProgressBar {{
    background: {BG_BTN};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}
"""
        )

        favicon_layout.addWidget(
            self.favicon_progress_label
        )
        favicon_layout.addWidget(
            self.favicon_progress_bar
        )

        self.favicon_progress_widget.setVisible(
            getattr(self, "_favicon_progress_running", False)
        )

        if getattr(self, "_favicon_progress_running", False):
            total = max(
                1,
                self._favicon_progress_total,
            )
            done = min(
                self._favicon_progress_done,
                total,
            )
            value = int(done * 100 / total)
            self.favicon_progress_bar.setValue(value)
            self.favicon_progress_label.setText(
                f"Favicons {value}%"
            )

        sidebar_layout.addWidget(
            self.favicon_progress_widget,
            alignment=Qt.AlignHCenter,
        )

        backup = VisualTile("sidebar")
        backup.setText("Backup")
        backup.setIcon(QIcon.fromTheme("document-save"))
        backup.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        backup.setIconSize(QSize(18, 18))
        backup.setFixedSize(66, 48)
        backup.setToolTip("Backup")
        backup.clicked.connect(self.create_backup)
        sidebar_layout.addWidget(backup, alignment=Qt.AlignHCenter)

        restore = VisualTile("sidebar")
        restore.setText("Restaurar")
        restore.setIcon(QIcon.fromTheme("document-open"))
        restore.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        restore.setIconSize(QSize(18, 18))
        restore.setFixedSize(66, 48)
        restore.setToolTip("Restaurar")
        restore.clicked.connect(self.restore_backup)
        sidebar_layout.addWidget(restore, alignment=Qt.AlignHCenter)

        shell_layout.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        topbar = QFrame()
        topbar.setProperty("role", "topbar")
        self.topbar = topbar
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(14, 7, 14, 7)
        topbar_layout.setSpacing(6)

        # alterado: layout linha-a-linha (cada linha centralizada por si só).
        # Substitui o QGridLayout, que deixava a última linha desalinhada à
        # esquerda sempre que o número de plataformas não fechava um retângulo
        # perfeito (ex.: 5 plataformas em 3 colunas -> 2ª linha com só 2 itens).
        platforms_wrap = QWidget()
        platforms_rows_layout = QVBoxLayout(platforms_wrap)
        platforms_rows_layout.setContentsMargins(0, 0, 0, 0)
        platforms_rows_layout.setSpacing(2)

        platform_columns = max(1, (len(PLATFORMS) + 1) // 2)
        platform_rows = [
            PLATFORMS[i : i + platform_columns] for i in range(0, len(PLATFORMS), platform_columns)
        ]
        for row_names in platform_rows:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            # alterado: espaçamento mínimo entre os ícones da barra (era 6px)
            row_layout.setSpacing(2)
            for name in row_names:
                status = self.launcher.get_platform_status(name)
                button = VisualTile("platform-tab")
                button.setProperty("active", name == selected_platform)
                button.setToolButtonStyle(Qt.ToolButtonIconOnly)
                button.setFixedSize(PLATFORM_TAB_WIDTH, PLATFORM_TAB_HEIGHT)
                button.setToolTip(name)
                pixmap = self.get_image(self.icon_path("platforms", name, status), PLATFORM_ICON)
                if pixmap:
                    button.setIcon(QIcon(pixmap))
                    # alterado: ícone +30% (era QSize(129, 42))
                    button.setIconSize(QSize(168, 55))
                else:
                    button.setText(name)
                    button.setToolButtonStyle(Qt.ToolButtonTextOnly)
                button.clicked.connect(lambda _checked=False, p=name: self.show_platform(p))

                if name == STATIC_PLATFORM:
                    platform_indicator = QLabel(button)
                    platform_indicator.setFixedSize(18, 18)
                    platform_indicator.move(
                        button.width() - 23,
                        5,
                    )
                    platform_indicator.setAlignment(Qt.AlignCenter)
                    platform_indicator.setAttribute(
                        Qt.WA_TransparentForMouseEvents,
                        True,
                    )
                    platform_indicator.setVisible(False)

                    button.resizeEvent = (
                        lambda event, b=button, i=platform_indicator:
                        (
                            QToolButton.resizeEvent(b, event),
                            i.move(b.width() - 23, 5),
                        )[0]
                    )

                    self._legalized_platform_indicator = platform_indicator

                row_layout.addWidget(button)
            # cada linha centralizada por conta própria, mesmo com menos itens que a de cima
            platforms_rows_layout.addWidget(row_widget, alignment=Qt.AlignHCenter)

        # alterado: bloco de plataformas centralizado na barra (era AlignLeft + addStretch(1))
        topbar_layout.addStretch(1)
        topbar_layout.addWidget(platforms_wrap, alignment=Qt.AlignVCenter)
        topbar_layout.addStretch(1)
        content_layout.addWidget(topbar)

        body = FadeIn()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 12, 18, 14)
        body_layout.setSpacing(10)
        content_layout.addWidget(body, 1)
        shell_layout.addWidget(content, 1)
        self.main_layout.addWidget(shell)
        return body, body_layout

    def _navehub_dir(self) -> Path:
        return self.launcher.base_dir.parent

    def _config_file(self) -> Path:
        return self._navehub_dir() / "config.json"

    def _running_profile_dirs(self) -> list[Path]:
        running = []
        platform_dirs = self.launcher.base_dir.iterdir() if self.launcher.base_dir.exists() else []
        for platform_dir in platform_dirs:
            if not platform_dir.is_dir():
                continue
            for profile_dir in platform_dir.iterdir():
                if profile_dir.is_dir() and self.launcher._profile_is_running(profile_dir):
                    running.append(profile_dir)
        return running

    def _ensure_accounts_closed(self, action: str) -> bool:
        running = self._running_profile_dirs()
        if not running:
            return True

        accounts = "\n".join(f"- {path.parent.name}/{path.name}" for path in running[:8])
        extra = "\n..." if len(running) > 8 else ""
        self.show_warning(
            action,
            "Feche todas as janelas de contas antes de continuar.\n\n"
            "Há perfis do Chromium em uso, e continuar agora pode gerar arquivos "
            f"incompletos ou corrompidos.\n\n{accounts}{extra}",
        )
        return False

    def _backup_manifest(self) -> dict:
        return {
            "format": "NaveHub Backup",
            "version": 3,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "contents": ["navehub"],
        }

    def _count_backup_files(self, root: Path) -> int:
        total = 0

        for current, dirs, files in os.walk(
            root,
            topdown=True,
            followlinks=False,
        ):
            current_path = Path(current)

            real_dirs = []
            for dirname in dirs:
                path = current_path / dirname
                if path.is_symlink():
                    continue
                real_dirs.append(dirname)
            dirs[:] = real_dirs

            for filename in files:
                path = current_path / filename
                if path.is_file() and not path.is_symlink():
                    total += 1

        return total

    def _create_backup_worker(self, target: Path):
        tmp_target = target.with_name(
            f".{target.name}.tmp"
        )

        try:
            navehub_dir = self._navehub_dir()

            self._backup_total_bytes = max(
                1,
                self._count_backup_files(navehub_dir),
            )
            self._backup_done_bytes = 0

            manifest_bytes = json.dumps(
                self._backup_manifest(),
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8")

            tmp_target.unlink(missing_ok=True)

            with tarfile.open(
                tmp_target,
                "w:gz",
                dereference=False,
            ) as backup:
                manifest_info = tarfile.TarInfo(
                    "manifest.json"
                )
                manifest_info.size = len(
                    manifest_bytes
                )
                manifest_info.mtime = (
                    datetime.now().timestamp()
                )

                backup.addfile(
                    manifest_info,
                    io.BytesIO(manifest_bytes),
                )

                if navehub_dir.exists():
                    backup.add(
                        navehub_dir,
                        arcname="navehub",
                        recursive=False,
                    )

                    for current, dirs, files in os.walk(
                        navehub_dir,
                        topdown=True,
                        followlinks=False,
                    ):
                        current_path = Path(current)
                        rel_current = current_path.relative_to(
                            navehub_dir
                        )

                        real_dirs = []

                        for dirname in sorted(dirs):
                            path = current_path / dirname

                            if path.is_symlink():
                                backup.add(
                                    path,
                                    arcname=str(
                                        Path("navehub")
                                        / rel_current
                                        / dirname
                                    ),
                                    recursive=False,
                                )
                                continue

                            real_dirs.append(dirname)

                        dirs[:] = real_dirs

                        for dirname in sorted(dirs):
                            path = current_path / dirname

                            backup.add(
                                path,
                                arcname=str(
                                    Path("navehub")
                                    / rel_current
                                    / dirname
                                ),
                                recursive=False,
                            )

                        for filename in sorted(files):
                            path = current_path / filename
                            arcname = str(
                                Path("navehub")
                                / rel_current
                                / filename
                            )

                            backup.add(
                                path,
                                arcname=arcname,
                                recursive=False,
                            )

                            if (
                                path.is_file()
                                and not path.is_symlink()
                            ):
                                self._backup_done_bytes += 1

            os.replace(
                tmp_target,
                target,
            )

            try:
                target.chmod(0o600)
            except OSError:
                pass

            self._backup_done_bytes = (
                self._backup_total_bytes
            )

        except Exception as error:
            self._backup_error = error

            try:
                tmp_target.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

    def create_backup(self):
        if (
            self._backup_thread is not None
            and self._backup_thread.is_alive()
        ):
            return

        if not self._ensure_accounts_closed("Backup"):
            return

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M"
        )

        filename, _selected = QFileDialog.getSaveFileName(
            self.window,
            "Salvar backup do NaveHub",
            f"navehub-backup-{timestamp}.tar.gz",
            "Backup completo do NaveHub (*.tar.gz);;Todos os arquivos (*.*)",
        )

        if not filename:
            return

        target = Path(filename)
        navehub_dir = self._navehub_dir().resolve()

        try:
            target_resolved = target.expanduser().resolve()

            if (
                target_resolved == navehub_dir
                or navehub_dir in target_resolved.parents
            ):
                self.show_error(
                    "Backup",
                    "O backup não pode ser salvo dentro de ~/.navehub.\n\n"
                    "Escolha outra pasta.",
                )
                return

        except OSError as error:
            self.show_error(
                "Backup",
                f"Não foi possível validar o destino.\n\n{error}",
            )
            return

        self._backup_total_bytes = 1
        self._backup_done_bytes = 0
        self._backup_error = None
        self._backup_target = target

        if hasattr(
            self,
            "backup_progress_widget",
        ):
            self.backup_progress_widget.setVisible(
                True
            )
            self.backup_progress_label.setText(
                "Backup 0%"
            )
            self.backup_progress_bar.setValue(
                0
            )

        self._backup_thread = threading.Thread(
            target=self._create_backup_worker,
            args=(target,),
            daemon=True,
        )

        self._backup_thread.start()

        QTimer.singleShot(
            100,
            self._poll_backup,
        )

    def _poll_backup(self):
        thread = self._backup_thread

        if (
            thread is not None
            and thread.is_alive()
        ):
            if hasattr(
                self,
                "backup_progress_bar",
            ):
                total = max(
                    1,
                    self._backup_total_bytes,
                )

                done = min(
                    self._backup_done_bytes,
                    total,
                )

                value = int(
                    done * 100 / total
                )

                self.backup_progress_bar.setValue(
                    value
                )
                self.backup_progress_label.setText(
                    f"Backup {value}%"
                )

            QTimer.singleShot(
                100,
                self._poll_backup,
            )
            return

        self._backup_thread = None

        error = self._backup_error
        target = self._backup_target

        self._backup_error = None
        self._backup_target = None

        if hasattr(
            self,
            "backup_progress_bar",
        ):
            self.backup_progress_bar.setValue(
                100
            )
            self.backup_progress_label.setText(
                "Backup 100%"
            )

        if error is not None:
            if hasattr(
                self,
                "backup_progress_widget",
            ):
                self.backup_progress_widget.setVisible(
                    False
                )

            self.show_error(
                "Backup",
                f"Não foi possível criar o backup.\n\n{error}",
            )
            return

        if hasattr(
            self,
            "backup_progress_widget",
        ):
            self.backup_progress_widget.setVisible(
                False
            )

        if target is not None:
            self.show_info(
                "Backup criado",
                f"Backup completo salvo em:\n{target}",
            )

    @staticmethod
    def _safe_extract_tar(backup: tarfile.TarFile, destination: Path):
        destination = destination.resolve()
        members = backup.getmembers()
        symlink_paths = set()

        for member in members:
            target = (destination / member.name).resolve()

            if target != destination and destination not in target.parents:
                raise ValueError("O backup contém caminhos inválidos.")

            if member.isdev() or member.islnk():
                raise ValueError(
                    "O backup contém arquivos especiais não suportados."
                )

            if member.issym():
                link_name = Path(member.linkname)

                if link_name.is_absolute():
                    raise ValueError("O backup contém links inválidos.")

                link_target = (target.parent / link_name).resolve()

                if (
                    link_target != destination
                    and destination not in link_target.parents
                ):
                    raise ValueError("O backup contém links inválidos.")

                symlink_paths.add(target)

        for member in members:
            target = (destination / member.name).resolve()

            if any(parent in symlink_paths for parent in target.parents):
                raise ValueError(
                    "O backup contém caminhos dentro de links."
                )

        backup.extractall(destination)

    def _extract_and_validate_backup(
        self,
        filename: Path,
        destination: Path,
    ):
        try:
            with tarfile.open(filename, "r:gz") as backup:
                self._safe_extract_tar(backup, destination)

        except tarfile.TarError as error:
            raise ValueError(
                "O arquivo selecionado não é um backup completo válido."
            ) from error

        manifest_file = destination / "manifest.json"
        navehub_source = destination / "navehub"

        if not manifest_file.is_file():
            raise ValueError(
                "O backup não contém manifest.json."
            )

        try:
            manifest = json.loads(
                manifest_file.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                "O manifest do backup está inválido."
            ) from error

        if (
            manifest.get("format") != "NaveHub Backup"
            or manifest.get("version") != 3
        ):
            raise ValueError(
                "Este backup não é compatível com a restauração completa."
            )

        if not navehub_source.is_dir():
            raise ValueError(
                "O backup não contém o diretório completo do NaveHub."
            )

    def _apply_complete_backup(self, extracted_dir: Path):
        current_navehub_dir = self._navehub_dir()
        backup_navehub_dir = extracted_dir / "navehub"

        parent_dir = current_navehub_dir.parent
        rollback_root = Path(
            tempfile.mkdtemp(
                prefix="navehub-rollback-",
                dir=parent_dir,
            )
        )

        rollback_target = rollback_root / "navehub"

        try:
            if current_navehub_dir.exists() or current_navehub_dir.is_symlink():
                shutil.move(
                    str(current_navehub_dir),
                    str(rollback_target),
                )

            shutil.move(
                str(backup_navehub_dir),
                str(current_navehub_dir),
            )

        except Exception:
            if (
                current_navehub_dir.exists()
                or current_navehub_dir.is_symlink()
            ):
                if (
                    current_navehub_dir.is_dir()
                    and not current_navehub_dir.is_symlink()
                ):
                    shutil.rmtree(current_navehub_dir)
                else:
                    current_navehub_dir.unlink()

            if rollback_target.exists() or rollback_target.is_symlink():
                shutil.move(
                    str(rollback_target),
                    str(current_navehub_dir),
                )

            raise

        finally:
            shutil.rmtree(
                rollback_root,
                ignore_errors=True,
            )

        self.config.clear()

        config_file = self._config_file()

        if config_file.exists():
            try:
                self.config.update(
                    json.loads(
                        config_file.read_text(
                            encoding="utf-8"
                        )
                    )
                )
            except (OSError, json.JSONDecodeError):
                pass

        self.launcher.base_dir = (
            self._navehub_dir() / "platforms"
        )
        self.launcher.base_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.launcher._initialization_marker = (
            self.launcher.base_dir / ".navehub_initialized"
        )

    def restore_backup(self):
        if (
            self._restore_thread is not None
            and self._restore_thread.is_alive()
        ):
            return

        filename, _selected = QFileDialog.getOpenFileName(
            self.window,
            "Restaurar backup do NaveHub",
            "",
            "Backup completo do NaveHub (*.tar.gz);;Todos os arquivos (*.*)",
        )

        if not filename:
            return

        if not self.ask_yes_no(
            "Substituir dados atuais?",
            "A restauração substituirá TODO o estado atual do NaveHub "
            "pelo estado salvo no backup.\n\n"
            "Nada da configuração atual será mesclado.\n"
            "Contas, logins, cookies, armazenamento, legendas, "
            "favicons, ordem e demais arquivos serão substituídos.\n\n"
            "Feche todas as janelas de contas antes de continuar.\n\n"
            "Continuar?",
        ):
            return

        if not self._ensure_accounts_closed("Restaurar backup"):
            return

        self._restore_error = None
        self._restore_source = Path(filename)
        self._restore_total = 1
        self._restore_done = 0

        if hasattr(self, "restore_progress_widget"):
            self.restore_progress_widget.setVisible(True)
            self.restore_progress_bar.setValue(0)
            self.restore_progress_label.setText("Restaurar 0%")

        self._restore_thread = threading.Thread(
            target=self._restore_backup_worker,
            args=(self._restore_source,),
            daemon=True,
        )

        self._restore_thread.start()

        QTimer.singleShot(100, self._poll_restore)

    def _restore_backup_worker(self, filename: Path):
        restore_temp = Path(
            tempfile.mkdtemp(
                prefix="navehub-restore-"
            )
        )

        try:
            with tarfile.open(
                filename,
                "r:gz",
            ) as backup:
                members = backup.getmembers()

            self._restore_total = max(
                1,
                len(members),
            )
            self._restore_done = 0

            with tarfile.open(
                filename,
                "r:gz",
            ) as backup:
                destination = restore_temp.resolve()
                members = backup.getmembers()
                symlink_paths = set()

                for member in members:
                    target = (
                        destination / member.name
                    ).resolve()

                    if (
                        target != destination
                        and destination not in target.parents
                    ):
                        raise ValueError(
                            "O backup contém caminhos inválidos."
                        )

                    if (
                        member.isdev()
                        or member.islnk()
                    ):
                        raise ValueError(
                            "O backup contém arquivos especiais não suportados."
                        )

                    if member.issym():
                        link_name = Path(
                            member.linkname
                        )

                        if link_name.is_absolute():
                            raise ValueError(
                                "O backup contém links inválidos."
                            )

                        link_target = (
                            target.parent
                            / link_name
                        ).resolve()

                        if (
                            link_target != destination
                            and destination not in link_target.parents
                        ):
                            raise ValueError(
                                "O backup contém links inválidos."
                            )

                        symlink_paths.add(target)

                for member in members:
                    target = (
                        destination / member.name
                    ).resolve()

                    if any(
                        parent in symlink_paths
                        for parent in target.parents
                    ):
                        raise ValueError(
                            "O backup contém caminhos dentro de links."
                        )

                    backup.extract(
                        member,
                        destination,
                    )

                    self._restore_done += 1

            # Valida o conteúdo já extraído sem extrair novamente.
            manifest_file = (
                restore_temp / "manifest.json"
            )
            navehub_source = (
                restore_temp / "navehub"
            )

            if not manifest_file.is_file():
                raise ValueError(
                    "O backup não contém manifest.json."
                )

            try:
                manifest = json.loads(
                    manifest_file.read_text(
                        encoding="utf-8"
                    )
                )
            except (
                OSError,
                json.JSONDecodeError,
            ) as error:
                raise ValueError(
                    "O manifest do backup está inválido."
                ) from error

            if (
                manifest.get("format")
                != "NaveHub Backup"
                or manifest.get("version")
                != 3
            ):
                raise ValueError(
                    "Este backup não é compatível com a restauração completa."
                )

            if not navehub_source.is_dir():
                raise ValueError(
                    "O backup não contém o diretório completo do NaveHub."
                )

            self._apply_complete_backup(
                restore_temp
            )

            self._restore_done = (
                self._restore_total
            )

        except Exception as error:
            self._restore_error = error

        finally:
            shutil.rmtree(
                restore_temp,
                ignore_errors=True,
            )

    def _poll_restore(self):
        thread = self._restore_thread

        if (
            thread is not None
            and thread.is_alive()
        ):
            self._restore_thread_progress_update()

            QTimer.singleShot(
                100,
                self._poll_restore,
            )
            return

        self._restore_thread = None

        error = self._restore_error

        self._restore_error = None
        self._restore_source = None

        if hasattr(
            self,
            "restore_progress_widget",
        ):
            self.restore_progress_bar.setValue(
                100
            )
            self.restore_progress_label.setText(
                "Restaurar 100%"
            )
            self.restore_progress_widget.setVisible(
                False
            )

        if error is not None:
            self.show_error(
                "Restaurar backup",
                "Não foi possível concluir a restauração.\n\n"
                f"{error}",
            )
            return

        self.image_cache.clear()

        self.launcher.base_dir = (
            self._navehub_dir() / "platforms"
        )
        self.launcher.base_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.show_platform_menu()

        self.show_info(
            "Restaurado",
            "O NaveHub foi restaurado exatamente para o estado "
            "salvo no backup.",
        )

    def _restore_thread_progress_update(self):
        if not hasattr(
            self,
            "restore_progress_bar",
        ):
            return

        total = max(
            1,
            self._restore_total,
        )

        done = min(
            self._restore_done,
            total,
        )

        value = int(
            done * 100 / total
        )

        self.restore_progress_bar.setValue(
            value
        )
        self.restore_progress_label.setText(
            f"Restaurar {value}%"
        )

    def _open_home_account(
        self,
        platform: str,
        profile_name: str,
    ):
        if self.launcher.launch_profile(
            platform,
            profile_name,
        ):
            if platform == STATIC_PLATFORM:
                self.launcher.start_profile_timer(
                    STATIC_PLATFORM,
                    profile_name,
                )

    def show_platform_menu(self):
        self.clear_frame()
        self.current_platform = None
        self.platform_toolbar = None
        self.platform_actions = None
        self.profiles_scroll = None
        self.window.setWindowTitle("NaveHub")

        _screen, layout = self._build_app_shell()

        accounts = []

        for platform in PLATFORMS:
            profiles = self.launcher.list_profiles(platform)

            for profile_name in profiles:
                if platform == STATIC_PLATFORM:
                    remaining = self.launcher.get_profile_timer_remaining(
                        STATIC_PLATFORM,
                        profile_name,
                    )

                    timer = self.launcher.get_profile_timer(
                        STATIC_PLATFORM,
                        profile_name,
                    )

                    duration = timer.get("duration_seconds", 0)
                    started_at = timer.get("started_at")

                    if (
                        duration > 0
                        and started_at is not None
                        and remaining <= 0
                    ):
                        accounts.append(
                            (
                                platform,
                                profile_name,
                                "B",
                            )
                        )

                elif self.launcher.get_profile_status(
                    platform,
                    profile_name,
                ) == "B":
                    accounts.append(
                        (
                            platform,
                            profile_name,
                            "B",
                        )
                    )

        layout.addStretch(1)

        if not accounts:
            empty_title = QLabel("Nenhuma conta disponível")
            empty_title.setStyleSheet(
                f"color: {FG}; font-size: 22px; font-weight: 700;"
            )

            empty_subtitle = QLabel(
                "Nenhuma conta está em estado B ou com contador zerado."
            )
            empty_subtitle.setStyleSheet(
                f"color: {FG_MUTED}; font-size: 10pt;"
            )

            layout.addWidget(
                empty_title,
                alignment=Qt.AlignHCenter,
            )
            layout.addWidget(
                empty_subtitle,
                alignment=Qt.AlignHCenter,
            )
        else:
            title = QLabel("Contas disponíveis")
            title.setStyleSheet(
                f"color: {FG}; font-size: 18px; font-weight: 700;"
            )

            layout.addWidget(
                title,
                alignment=Qt.AlignHCenter,
            )

            accounts_widget = QWidget()
            accounts_grid = QGridLayout(accounts_widget)
            accounts_grid.setContentsMargins(
                0,
                16,
                0,
                0,
            )
            accounts_grid.setHorizontalSpacing(
                self.grid.horizontalSpacing()
                if hasattr(self, "grid")
                else GRID_HORIZONTAL_SPACING
            )
            accounts_grid.setVerticalSpacing(
                self.grid.verticalSpacing()
                if hasattr(self, "grid")
                else GRID_VERTICAL_SPACING
            )

            columns = 6

            for index, (
                platform,
                profile_name,
                status,
            ) in enumerate(accounts):
                card = QWidget()
                card.setFixedSize(
                    ACCOUNT_TILE_WIDTH,
                    LEGALIZED_ACCOUNT_TILE_HEIGHT,
                )

                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(
                    0,
                    0,
                    0,
                    0,
                )
                card_layout.setSpacing(3)

                button = QToolButton(card)
                button.setProperty("role", "account")
                button.setFixedSize(
                    ACCOUNT_TILE_WIDTH,
                    ACCOUNT_TILE_HEIGHT,
                )
                button.setToolButtonStyle(
                    Qt.ToolButtonTextUnderIcon
                )

                display = self.launcher.get_profile_display_name(
                    platform,
                    profile_name,
                )

                button.setText(display)

                pixmap = self.get_image(
                    self.account_icon_path(
                        platform,
                        profile_name,
                        status,
                    ),
                    ACCOUNT_ICON,
                )

                if pixmap is not None:
                    button.setIcon(QIcon(pixmap))
                    button.setIconSize(
                        QSize(*ACCOUNT_CARD_ICON)
                    )

                button.clicked.connect(
                    lambda _checked=False,
                    p=platform,
                    n=profile_name:
                    self._open_home_account(p, n)
                )

                card_layout.addWidget(button)

                if platform == STATIC_PLATFORM:
                    indicator = QLabel(card)
                    indicator.setFixedSize(
                        10,
                        10,
                    )
                    indicator.move(
                        ACCOUNT_TILE_WIDTH - 15,
                        5,
                    )
                    indicator.setAttribute(
                        Qt.WA_TransparentForMouseEvents,
                        True,
                    )
                    indicator.setStyleSheet(
                        "background: #ff3b30; border-radius: 5px;"
                    )

                row, col = divmod(
                    index,
                    columns,
                )

                accounts_grid.addWidget(
                    card,
                    row,
                    col,
                )

            accounts_scroll = QScrollArea()
            accounts_scroll.setWidgetResizable(True)
            accounts_scroll.setFrameShape(QFrame.NoFrame)
            accounts_scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarAlwaysOff
            )
            accounts_scroll.setVerticalScrollBarPolicy(
                Qt.ScrollBarAlwaysOff
            )
            accounts_scroll.setWidget(accounts_widget)
            accounts_scroll.setMaximumHeight(
                max(
                    240,
                    self.window.screen().availableGeometry().height() - 260,
                )
            )

            layout.addWidget(
                accounts_scroll,
                alignment=Qt.AlignHCenter,
            )

        layout.addStretch(2)
        self.fit_window_to_content()

    def update_static_platform_favicons(self):
        profiles = self.launcher.list_profiles(
            STATIC_PLATFORM
        )

        self._favicon_progress_total = len(profiles)
        self._favicon_progress_done = 0
        self._favicon_progress_running = True

        if hasattr(self, "favicon_progress_widget"):
            self.favicon_progress_widget.setVisible(True)
            self.favicon_progress_bar.setValue(0)
            self.favicon_progress_label.setText(
                "Favicons 0%"
            )

        def progress(profile_name, status, result):
            done = (
                result.get("updated", 0)
                + result.get("skipped", 0)
                + result.get("failed", 0)
            )

            self._favicon_signals.progress.emit(done)

        def complete(result):
            self._favicon_signals.complete.emit(result)

        started = self.launcher.enqueue_static_platform_favicons(
            force=True,
            on_progress=progress,
            on_complete=complete,
        )

        if not started:
            self._favicon_progress_running = False

            if hasattr(self, "favicon_progress_widget"):
                self.favicon_progress_widget.setVisible(False)

            self.show_warning(
                "Favicons em andamento",
                "Já existe uma atualização de Favicons em processamento.",
            )

    def _update_favicon_progress(self, done: int):
        total = max(
            1,
            self._favicon_progress_total,
        )

        done = min(
            done,
            total,
        )

        self._favicon_progress_done = done
        self._favicon_progress_running = True

        value = int(
            done * 100 / total
        )

        if hasattr(self, "favicon_progress_bar"):
            self.favicon_progress_bar.setValue(value)
            self.favicon_progress_label.setText(
                f"Favicons {value}%"
            )

    def _finish_static_favicon_update(self, result: dict):
        self._favicon_progress_done = (
            self._favicon_progress_total
        )
        self._favicon_progress_running = False

        if hasattr(self, "favicon_progress_bar"):
            self.favicon_progress_bar.setValue(100)
            self.favicon_progress_label.setText(
                "Favicons 100%"
            )

        self.image_cache.clear()

        if self.current_platform == STATIC_PLATFORM:
            self.load_profiles()

        if hasattr(self, "favicon_progress_widget"):
            self.favicon_progress_widget.setVisible(True)

        self.show_info(
            "Favicons atualizados",
            "Sincronização concluída para Legalizadas.\n\n"
            f"Atualizados: {result['updated']}\n"
            f"Sem URL válida: {result['skipped']}\n"
            f"Falhas: {result['failed']}",
        )

    def preload_profile_icons(self, platform: str, profiles: list[str]):
        paths = {
            self.account_icon_path(platform, profile_name, self.launcher.get_profile_status(platform, profile_name))
            for profile_name in profiles
        }
        for path in paths:
            self.get_image(path, ACCOUNT_ICON)

    def enqueue_missing_static_favicons(self, profiles: list[str]):
        missing = [
            profile_name
            for profile_name in profiles
            if self.launcher.get_profile_icon_path(STATIC_PLATFORM, profile_name) is None
        ]
        if not missing:
            return

        remaining = len(missing)

        def complete(_result):
            nonlocal remaining
            remaining -= 1
            if remaining <= 0:
                QTimer.singleShot(0, self._refresh_static_favicon_icons)

        for profile_name in missing:
            if not self.launcher.enqueue_static_profile_favicon(profile_name, on_complete=complete):
                remaining -= 1
        if remaining == 0:
            self._refresh_static_favicon_icons()

    def _refresh_static_favicon_icons(self):
        if self.current_platform != STATIC_PLATFORM:
            return
        self.image_cache.clear()
        self.load_profiles()

    def show_platform(self, platform_name: str):
        profiles = self.launcher.list_profiles(platform_name)
        self.preload_profile_icons(platform_name, profiles)

        self.clear_frame()
        self.current_platform = platform_name
        self._profile_order = profiles[:]
        self.window.setWindowTitle("NaveHub")

        _screen, layout = self._build_app_shell(platform_name)

        toolbar = QWidget()
        self.platform_toolbar = toolbar
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(6)
        toolbar_layout.addStretch(1)
        layout.addWidget(toolbar)

        self.profiles_frame = QWidget()
        self.grid = QGridLayout(self.profiles_frame)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(GRID_HORIZONTAL_SPACING)
        self.grid.setVerticalSpacing(GRID_VERTICAL_SPACING)
        self.grid.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.profiles_scroll = QScrollArea()
        self.profiles_scroll.setWidgetResizable(True)
        self.profiles_scroll.setFrameShape(QFrame.NoFrame)
        self.profiles_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.profiles_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.profiles_scroll.setWidget(self.profiles_frame)
        layout.addWidget(self.profiles_scroll, 1)

        actions = QWidget()
        self.platform_actions = actions
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)

        if platform_name == STATIC_PLATFORM:
            favicons = self.btn(
                actions,
                "Atualizar Favicons",
                self.update_static_platform_favicons,
            )
            actions_layout.addWidget(
                favicons,
                alignment=Qt.AlignLeft,
            )

        actions_layout.addStretch(1)

        if platform_name != STATIC_PLATFORM:
            reset = self.btn(
                actions,
                "↺  Resetar",
                self.reset_platform_statuses,
                variant="warning",
            )
            actions_layout.addWidget(
                reset,
                alignment=Qt.AlignRight,
            )

        add = self.btn(
            actions,
            "＋  Nova conta",
            self.add_new_profile,
            variant="primary",
        )
        actions_layout.addWidget(
            add,
            alignment=Qt.AlignRight,
        )

        layout.addWidget(actions)

        self.load_profiles(profiles)
        if platform_name == STATIC_PLATFORM:
            self.enqueue_missing_static_favicons(profiles)

    def load_profiles(self, profiles: list[str] | None = None):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if profiles is None:
            profiles = self.launcher.list_profiles(self.current_platform)
        self._profile_order = profiles[:]
        self._account_items = {}
        if not profiles:
            empty = QLabel("Nenhuma conta nesta plataforma")
            empty.setStyleSheet(f"color: {FG_MUTED};")
            self.grid.addWidget(empty, 0, 0, alignment=Qt.AlignCenter)
            self.fit_window_to_content()
            return

        self._laying_out_profiles = True
        try:
            max_columns = min(9, PLATFORM_COLUMNS.get(self.current_platform, COLS))
            self._natural_grid_columns = max(1, min(max_columns, len(profiles)))
            columns = self.grid_columns()

            if self.current_platform == STATIC_PLATFORM:
                columns = min(columns + 1, 10)
            rows = (len(profiles) + columns - 1) // columns
            horizontal_spacing = self.grid.horizontalSpacing()
            vertical_spacing = self.grid.verticalSpacing()
            grid_width = columns * ACCOUNT_TILE_WIDTH + (columns - 1) * horizontal_spacing
            tile_height = (
                LEGALIZED_ACCOUNT_TILE_HEIGHT
                if self.current_platform == STATIC_PLATFORM
                else ACCOUNT_TILE_HEIGHT
            )
            grid_height = rows * tile_height + (rows - 1) * vertical_spacing
            self.profiles_frame.setMinimumSize(grid_width, grid_height)
            if self.profiles_scroll is not None:
                self.profiles_scroll.setMinimumWidth(grid_width)
                self.profiles_scroll.setMinimumHeight(0)
            for index, name in enumerate(profiles):
                button = self._build_account_button(name)
                self._account_items[name] = button
                row, col = divmod(index, columns)
                self.grid.addWidget(button, row, col)
            for col in range(columns):
                self.grid.setColumnStretch(col, 1)
        finally:
            self._laying_out_profiles = False
        self.fit_window_to_content()

    def _relayout_profiles(self):
        if not self._profile_order or not hasattr(self, "grid"):
            return
        self._layout_profile_order(self._profile_order)

    @staticmethod
    def _format_countdown(seconds: int) -> str:
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _parse_countdown(text: str) -> int | None:
        text = text.strip()

        if not text:
            return 0

        try:
            minutes = int(text)
        except ValueError:
            return None

        if minutes < 0:
            return None

        return minutes * 60

    def _count_zeroed_legalized_timers(self) -> int:
        count = 0

        for profile_name in self.launcher.list_profiles(STATIC_PLATFORM):
            timer = self.launcher.get_profile_timer(
                STATIC_PLATFORM,
                profile_name,
            )

            duration = timer.get("duration_seconds", 0)
            started_at = timer.get("started_at")

            if duration > 0 and started_at is not None:
                remaining = self.launcher.get_profile_timer_remaining(
                    STATIC_PLATFORM,
                    profile_name,
                )

                if remaining <= 0:
                    count += 1

        return count

    def _update_legalized_platform_indicator(self):
        indicator = getattr(
            self,
            "_legalized_platform_indicator",
            None,
        )

        if indicator is None:
            return

        count = self._count_zeroed_legalized_timers()

        if count > 0:
            indicator.setText(str(count))
            indicator.setVisible(True)
            indicator.setStyleSheet(
                """
QLabel {
    background: #ff3b30;
    color: white;
    border-radius: 9px;
    font-size: 8px;
    font-weight: 800;
    padding: 0px;
}
"""
            )
            indicator.setAlignment(Qt.AlignCenter)
        else:
            indicator.setText("")
            indicator.setVisible(False)

    def _update_timer_indicator(
        self,
        profile_name: str,
        editor: QLineEdit,
    ):
        card = editor.parentWidget()
        if card is None:
            return

        indicator = getattr(card, "_timer_indicator", None)
        if indicator is None:
            return

        timer = self.launcher.get_profile_timer(
            STATIC_PLATFORM,
            profile_name,
        )

        duration = timer.get("duration_seconds", 0)
        started_at = timer.get("started_at")

        remaining = self.launcher.get_profile_timer_remaining(
            STATIC_PLATFORM,
            profile_name,
        )

        if remaining <= 0 and duration > 0 and started_at is not None:
            indicator.setStyleSheet(
                "background: #ff3b30; border-radius: 5px;"
            )
            indicator.setToolTip("Contador finalizado")
        elif started_at is not None and remaining > 0:
            indicator.setStyleSheet(
                "background: #34c759; border-radius: 5px;"
            )
            indicator.setToolTip("Contador em andamento")
        else:
            indicator.setStyleSheet(
                "background: #777777; border-radius: 5px;"
            )
            indicator.setToolTip("Contador aguardando abertura")

    def _refresh_legalized_timers(self):
        if self.current_platform != STATIC_PLATFORM:
            self._update_legalized_platform_indicator()
            return

        for profile_name, editor in self._legalized_timer_editors.items():
            if editor.hasFocus():
                continue

            remaining = self.launcher.get_profile_timer_remaining(
                STATIC_PLATFORM,
                profile_name,
            )

            editor.setText(
                self._format_countdown(remaining)
            )

            self._update_timer_indicator(
                profile_name,
                editor,
            )

        self._update_legalized_platform_indicator()

    def _prepare_timer_editor(
        self,
        editor: QLineEdit,
    ):
        if not editor.property("_timer_editing"):
            editor.setProperty("_timer_editing", True)
            editor.clear()

    def _finish_timer_editor(
        self,
        editor: QLineEdit,
    ):
        editor.setProperty("_timer_editing", False)

    def _save_legalized_timer(
        self,
        profile_name: str,
        editor: QLineEdit,
    ):
        value = self._parse_countdown(editor.text())

        if value is None:
            editor.setText(
                self._format_countdown(
                    self.launcher.get_profile_timer_remaining(
                        STATIC_PLATFORM,
                        profile_name,
                    )
                )
            )
            return

        self.launcher.set_profile_timer(
            STATIC_PLATFORM,
            profile_name,
            value,
        )

        editor.setText(
            self._format_countdown(value)
        )

    def _build_account_button(self, profile_name: str):
        status = self.launcher.get_profile_status(self.current_platform, profile_name)
        display = self.launcher.get_profile_display_name(self.current_platform, profile_name)
        button = AccountButton(profile_name, self)
        button.setProperty("role", "account")
        button.setProperty("status", status)
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setText(display)
        tile_height = (
            LEGALIZED_ACCOUNT_TILE_HEIGHT
            if self.current_platform == STATIC_PLATFORM
            else ACCOUNT_TILE_HEIGHT
        )
        button.setMinimumSize(ACCOUNT_TILE_WIDTH, tile_height)
        button.setMaximumSize(ACCOUNT_TILE_WIDTH, tile_height)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        button.setIconSize(QSize(*ACCOUNT_CARD_ICON))
        button.setToolTip(f"{display} · Status {status}")
        pixmap = self.get_image(self.account_icon_path(self.current_platform, profile_name, status), ACCOUNT_ICON)
        if pixmap:
            button.setIcon(QIcon(pixmap))
            button.setIconSize(QSize(*ACCOUNT_CARD_ICON))
        else:
            button.setText(f"{display}\n[{status}]")
        if self.current_platform == STATIC_PLATFORM:
            timer_editor = QLineEdit(button)
            timer_editor.setAlignment(Qt.AlignCenter)
            timer_editor.setGeometry(
                3,
                LEGALIZED_ACCOUNT_TILE_HEIGHT - 25,
                ACCOUNT_TILE_WIDTH - 6,
                21,
            )
            timer_editor.setText(
                self._format_countdown(
                    self.launcher.get_profile_timer_remaining(
                        STATIC_PLATFORM,
                        profile_name,
                    )
                )
            )
            timer_editor.setPlaceholderText("00:00:00")
            timer_editor.setMaxLength(8)
            timer_editor.setStyleSheet(
                f"""
QLineEdit {{
    background: {BG_BTN};
    color: {FG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 1px 2px;
    font-size: 8px;
    font-weight: 700;
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
"""
            )
            timer_editor.mousePressEvent = (
                lambda event, e=timer_editor:
                (
                    self._prepare_timer_editor(e),
                    QLineEdit.mousePressEvent(e, event),
                )[-1]
            )

            timer_editor.returnPressed.connect(
                lambda p=profile_name, e=timer_editor:
                self._save_legalized_timer(p, e)
            )

            timer_editor.editingFinished.connect(
                lambda p=profile_name, e=timer_editor:
                self._save_legalized_timer(p, e)
            )

            timer_editor.editingFinished.connect(
                lambda e=timer_editor:
                self._finish_timer_editor(e)
            )

            timer_indicator = QLabel(button)
            timer_indicator.setFixedSize(10, 10)
            timer_indicator.move(
                ACCOUNT_TILE_WIDTH - 15,
                5,
            )
            timer_indicator.setAttribute(
                Qt.WA_TransparentForMouseEvents,
                True,
            )

            card = timer_editor.parentWidget()
            if card is not None:
                card._timer_indicator = timer_indicator

            self._legalized_timer_editors[profile_name] = timer_editor

            self._update_timer_indicator(
                profile_name,
                timer_editor,
            )

        button.clicked.connect(
            lambda _checked=False, p=profile_name: self.open_profile(p)
        )
        return button

    def move_profile_to_pointer(self, profile_name: str, global_pos: QPoint):
        if profile_name not in self._profile_order:
            return
        closest_index = None
        closest_distance = float("inf")
        for index, name in enumerate(self._profile_order):
            widget = self._account_items.get(name)
            if widget is None:
                continue
            center = widget.mapToGlobal(widget.rect().center())
            distance = (center.x() - global_pos.x()) ** 2 + (center.y() - global_pos.y()) ** 2
            if distance < closest_distance:
                closest_index = index
                closest_distance = distance
        if closest_index is None:
            return
        source_index = self._profile_order.index(profile_name)
        if source_index == closest_index:
            return
        order = self._profile_order[:]
        order.pop(source_index)
        order.insert(closest_index, profile_name)
        self._profile_order = order
        self._layout_profile_order(order)

    def _layout_profile_order(self, order: list[str]):
        for index, name in enumerate(order):
            widget = self._account_items[name]
            row, col = divmod(index, self.grid_columns())
            self.grid.addWidget(widget, row, col)

    def open_profile(self, profile_name: str):
        if self.launcher.launch_profile(self.current_platform, profile_name):
            if self.current_platform == STATIC_PLATFORM:
                self.launcher.start_profile_timer(
                    STATIC_PLATFORM,
                    profile_name,
                )
                self._refresh_legalized_timers()
            self.load_profiles()
        else:
            self.show_error("Erro", f"Navegador '{self.config.get('browser')}' não encontrado.")

    def reset_platform_statuses(self):
        platform = self.current_platform
        if not platform or platform == STATIC_PLATFORM:
            return
        if not self.ask_yes_no(
            "Resetar A/B",
            f"Resetar o status A/B de todas as contas de {platform}?\n\n"
            "Todas voltarão para B. Login, site e ordem não serão alterados.",
        ):
            return

        changed = self.launcher.reset_profile_statuses(platform)
        self.load_profiles()
        self.show_info("Status resetado", f"{changed} conta(s) voltaram ao status B.")

    def add_new_profile(self):
        self._account_dialog(mode="create")

    def edit_profile(self, profile_name: str):
        self._account_dialog(mode="edit", profile_name=profile_name)

    def clone_profile(self, profile_name: str):
        cloned_profile = self.launcher.clone_profile(self.current_platform, profile_name)
        if cloned_profile is None:
            self.show_error("Erro", "Não foi possível clonar esta conta.")
            return

        self.load_profiles()
        self._account_dialog(mode="edit", profile_name=cloned_profile)

    def heavy_clean_profile(self, profile_name: str):
        display = self.launcher.get_profile_display_name(self.current_platform, profile_name)
        if not self.ask_yes_no(
            "Limpeza pesada",
            f"Apagar completamente os dados locais da conta '{display}'?\n\n"
            "Cookies, cache, storage e demais dados do navegador serão removidos. "
            "A conta continuará cadastrada no NaveHub com a mesma legenda e ícone.",
        ):
            return

        if self.launcher.heavy_clean_profile(self.current_platform, profile_name):
            self.load_profiles()
        else:
            self.show_error("Erro", "Não foi possível limpar esta conta.")

    def delete_profile(self, profile_name: str):
        display = self.launcher.get_profile_display_name(self.current_platform, profile_name)
        if self.ask_yes_no(
            "Confirmar Exclusão",
            f"Deseja realmente excluir a conta '{display}'?\nTodos os dados serão perdidos.",
        ):
            if self.launcher.delete_profile(self.current_platform, profile_name):
                self.load_profiles()

    def _account_dialog(self, mode: str, profile_name: str | None = None):
        is_edit = mode == "edit"
        dialog = QDialog(self.window)
        dialog.setWindowTitle("NaveHub")
        dialog.setFixedSize(420, 315)
        dialog.setStyleSheet(QT_STYLE)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 22, 24, 20)
        title = QLabel("Editar conta" if is_edit else "Nova conta")
        title.setStyleSheet(f"color: {FG}; font-size: 15px; font-weight: 700;")
        subtitle = QLabel("Defina como esta conta aparecerá no NaveHub.")
        subtitle.setStyleSheet(f"color: {FG_MUTED}; font-size: 9pt;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        current_display = (
            self.launcher.get_profile_display_name(self.current_platform, profile_name)
            if is_edit
            else ""
        )
        current_site = (
            self.launcher.get_profile_homepage(self.current_platform, profile_name)
            if is_edit
            else self.launcher.get_default_homepage(self.current_platform)
            or self.config.get("homepage", "https://site.com")
        )

        name_label = QLabel("Nome da conta:")
        name_label.setStyleSheet(f"color: {FG_MUTED}; font-weight: 700;")
        name_entry = QLineEdit(current_display)
        site_label = QLabel("Site da conta:")
        site_label.setStyleSheet(f"color: {FG_MUTED}; font-weight: 700;")
        site_entry = QLineEdit(current_site)
        layout.addSpacing(10)
        layout.addWidget(name_label)
        layout.addWidget(name_entry)
        layout.addWidget(site_label)
        layout.addWidget(site_entry)
        layout.addStretch(1)

        actions = QFrame()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        save_button = self.btn(actions, "Salvar" if is_edit else "Criar", lambda: None, variant="primary")
        cancel_button = self.btn(actions, "Cancelar", dialog.reject, variant="ghost")
        actions_layout.addWidget(save_button)
        actions_layout.addWidget(cancel_button)
        actions_layout.addStretch(1)
        layout.addWidget(actions)

        if not is_edit:
            name_entry.setFocus()

        def save():
            name = name_entry.text().strip()
            site = site_entry.text().strip()
            if is_edit:
                if not name or not site:
                    self.show_warning("Aviso", "Nome e site são obrigatórios.")
                    return
                target = profile_name
                if name != current_display:
                    if not self.launcher.rename_profile(self.current_platform, profile_name, name):
                        self.show_error("Erro", "Não foi possível renomear.")
                        return
                    target = name
                self.launcher.set_profile_display_name(self.current_platform, target, name)
                self.launcher.set_profile_homepage(self.current_platform, target, site)
            else:
                if not name:
                    self.show_warning("Aviso", "Digite o nome da conta.")
                    return
                homepage = site or self.launcher.get_profile_homepage(self.current_platform, name)
                self.launcher.create_profile(self.current_platform, name, homepage=homepage)
                self.launcher.set_profile_display_name(self.current_platform, name, name)

            self.load_profiles()
            dialog.accept()

        try:
            save_button.clicked.disconnect()
        except RuntimeError:
            pass
        save_button.clicked.connect(save)
        dialog.exec()