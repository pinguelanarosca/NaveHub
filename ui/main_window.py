import io
import json
import shutil
import tarfile
import tempfile
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Any, cast

from PIL import Image, ImageTk

from launcher.profile_launcher import STATIC_PLATFORM, ProfileLauncher

BG = "#050608"
SURFACE = "#0A0D12"
SURFACE_ELEVATED = "#0D1118"
CARD = "#0A0D12"
CARD_HOVER = "#111824"
BG_BTN = "#0D1118"
BG_HOVER = "#141B27"
FG = "#F3F6F8"
FG_MUTED = "#93A0AE"
BORDER = "#1D2633"
ACCENT = "#34C6A8"
ACCENT_HOVER = "#59D3BB"
ACCENT_TEXT = "#FFFFFF"
SUCCESS = "#34D399"
WARNING = "#E0A84A"
DANGER = "#F06B7E"
DANGER_HOVER = "#E85C70"

PLATFORMS = ("8U", "777", "365GG", "93H", STATIC_PLATFORM)
PLATFORM_ICON = (300, 98)
ACCOUNT_ICON = (70, 70)
PLATFORM_COLUMNS = {
    "8U": 5,
    "777": 4,
    "365GG": 4,
    "93H": 4,
    STATIC_PLATFORM: 5,
}
COLS = 5
WINDOW_RESIZE_STEPS = 10
WINDOW_RESIZE_INTERVAL_MS = 16
DRAG_HOLD_MS = 220
DRAG_THRESHOLD = 8
ACCOUNT_CARD_WIDTH = 78
ACCOUNT_CARD_HEIGHT = 84
GRID_CARD_PAD_X = 2
GRID_CARD_PAD_Y = 2
WINDOW_CONTENT_MARGIN = 12


class RoundedButton(tk.Canvas):
    """Botão leve com cantos arredondados, independente do tema do sistema."""

    def __init__(self, parent, text, command, normal_bg, hover_bg, foreground,
                 width=None, height=None):
        self.text = text
        self.command = command
        self.normal_bg = normal_bg
        self.hover_bg = hover_bg
        self.foreground = foreground
        self.radius = 8
        self.font = ("Arial", 8, "bold")
        measure = tkfont.Font(font=self.font)
        calculated_width = measure.measure(text) + 20
        if width is not None:
            calculated_width = max(calculated_width, width * 8 + 12)
        self.button_width = calculated_width
        self.button_height = height or 30
        super().__init__(
            parent,
            width=self.button_width,
            height=self.button_height,
            bg=parent.cget("bg"),
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.bind("<Enter>", lambda _event: self._draw(self.hover_bg))
        self.bind("<Leave>", lambda _event: self._draw(self.normal_bg))
        self.bind("<ButtonPress-1>", lambda _event: self._draw(self.hover_bg))
        self.bind("<ButtonRelease-1>", self._release)
        self._draw(self.normal_bg)

    def _rounded_rectangle(self, color):
        x1, y1 = 0, 0
        x2, y2 = self.button_width, self.button_height
        r = self.radius
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=color, outline="")
        self.create_rectangle(x1, y1 + r, x2, y2 - r, fill=color, outline="")
        self.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90,
                        fill=color, outline="")
        self.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90,
                        fill=color, outline="")
        self.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90,
                        fill=color, outline="")
        self.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90,
                        fill=color, outline="")

    def _draw(self, color):
        self.delete("all")
        self._rounded_rectangle(color)
        self.create_text(
            self.button_width // 2,
            self.button_height // 2,
            text=self.text,
            fill=self.foreground,
            font=self.font,
        )

    def _release(self, event):
        inside = 0 <= event.x <= self.button_width and 0 <= event.y <= self.button_height
        self._draw(self.hover_bg if inside else self.normal_bg)
        if inside:
            self.command()


class NaveHubDialog:
    def __init__(self, parent, title, message, *, kind="info", buttons=(("OK", True, "primary"),), width=430):
        self.result = None
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.geometry(f"{width}x220")
        self.win.configure(bg=SURFACE)
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        frame = tk.Frame(self.win, bg=SURFACE)
        frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=16)

        accent = {"info": ACCENT, "warning": WARNING, "error": DANGER}.get(kind, ACCENT)
        title_row = tk.Frame(frame, bg=SURFACE)
        title_row.pack(fill=tk.X, anchor="w")
        tk.Label(title_row, text=title, bg=SURFACE, fg=FG, font=("Arial", 12, "bold")).pack(anchor="w")
        tk.Label(frame, text=message, bg=SURFACE, fg=FG_MUTED, font=("Arial", 9), justify="left", wraplength=width - 36).pack(anchor="w", pady=(8, 14))

        actions = tk.Frame(frame, bg=SURFACE)
        actions.pack(fill=tk.X, side=tk.BOTTOM)
        for label, value, variant in buttons:
            self.parent = parent
            self._add_button(actions, label, value, variant, accent)

        self.win.update_idletasks()
        x = max(0, (parent.winfo_screenwidth() - self.win.winfo_width()) // 2)
        y = max(0, (parent.winfo_screenheight() - self.win.winfo_height()) // 2)
        self.win.geometry(f"{self.win.winfo_width()}x{self.win.winfo_height()}+{x}+{y}")
        self.win.wait_window()

    def _add_button(self, parent, label, value, variant, accent):
        def action():
            self.result = value
            self._close()
        color_map = {
            "primary": (ACCENT, ACCENT_HOVER, ACCENT_TEXT),
            "danger": (DANGER, DANGER_HOVER, FG),
            "ghost": (SURFACE, SURFACE_ELEVATED, FG_MUTED),
            "secondary": (BG_BTN, BG_HOVER, FG),
        }
        normal_bg, hover_bg, fg = color_map.get(variant, color_map["secondary"])
        btn = RoundedButton(parent, label, action, normal_bg, hover_bg, fg)
        btn.pack(side=tk.RIGHT, padx=(6, 0))

    def _close(self):
        try:
            self.win.grab_release()
        except tk.TclError:
            pass
        self.win.destroy()




class MainWindow:
    def __init__(self, config):
        self.config = config
        self.launcher = ProfileLauncher(config)
        self.current_platform = None
        self.image_cache = {}
        self.open_context_menu = None
        self.resize_animation = None
        self.is_initial_layout = True
        self._profile_order = []
        self._account_items = {}
        self._account_widgets = {}
        self._drag_state = None
        self._drag_after = None
        self.profiles_canvas = None

        base = Path(__file__).parent.parent
        self.icons_platforms = base / "icons" / "platforms"
        self.icons_accounts = base / "icons" / "accounts"
        self.icons_platforms.mkdir(parents=True, exist_ok=True)
        self.icons_accounts.mkdir(parents=True, exist_ok=True)

        # className=NaveHub → WM_CLASS bate com StartupWMClass do .desktop (dock não duplica ícone)
        self.root = tk.Tk(className="NaveHub")
        self.root.title("NaveHub")
        self.root.geometry("1x1")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        try:
            self.app_icon = tk.PhotoImage(file=base / "icons" / "navehub" / "icondocnavegunb.png")
            self.root.iconphoto(True, self.app_icon)
        except tk.TclError:
            self.app_icon = None
        try:
            self.root.tk.call("tk", "appname", "NaveHub")
        except tk.TclError:
            pass

        self.center_account_windows()

        self.main_frame = tk.Frame(self.root, bg=BG)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.show_platform_menu()

    # ── helpers ──────────────────────────────────────────────

    def clear_frame(self):
        for w in self.main_frame.winfo_children():
            w.destroy()

    def show_dialog(self, title: str, message: str, *, kind="info", buttons=(("OK", True, "primary"),), width=430):
        return NaveHubDialog(self.root, title, message, kind=kind, buttons=buttons, width=width).result

    def show_info(self, title: str, message: str):
        self.show_dialog(title, message, kind="info")

    def show_error(self, title: str, message: str):
        self.show_dialog(title, message, kind="error")

    def show_warning(self, title: str, message: str):
        self.show_dialog(title, message, kind="warning")

    def ask_yes_no(self, title: str, message: str) -> bool:
        return bool(self.show_dialog(title, message, kind="warning", buttons=(("Não", False, "ghost"), ("Sim", True, "danger")), width=500))

    def center_account_windows(self):
        """Centraliza as janelas Chrome das contas na tela atual."""
        width, height = self.launcher.get_window_size()
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2)
        self.launcher.set_window_position(x, y)

    def set_window_geometry(self, width: int, height: int, *, centered=False):
        """Aplica a geometria e centraliza somente na abertura inicial."""
        if centered:
            x = max(0, (self.root.winfo_screenwidth() - width) // 2)
            y = max(0, (self.root.winfo_screenheight() - height) // 2)
            self.root.geometry(f"{width}x{height}+{x}+{y}")
            return
        self.root.geometry(f"{width}x{height}")

    def fit_window_to_content(self):
        """Define a geometria da janela pelo tamanho requisitado do conteúdo."""
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        target_width = min(max(1, self.main_frame.winfo_reqwidth()), max(320, screen_width - 36))
        target_height = min(max(1, self.main_frame.winfo_reqheight()), max(240, screen_height - 72))

        if self.resize_animation is not None:
            self.root.after_cancel(self.resize_animation)
            self.resize_animation = None

        # A primeira montagem deve ser centralizada mesmo quando o Tk já
        # preparou a janela durante update_idletasks().
        if self.is_initial_layout:
            self.is_initial_layout = False
            self.set_window_geometry(target_width, target_height, centered=True)
            return

        current_width = self.root.winfo_width()
        current_height = self.root.winfo_height()
        if (current_width, current_height) == (target_width, target_height):
            return

        def animate(step=1):
            progress = step / WINDOW_RESIZE_STEPS
            # Ease-out: inicia perceptível e desacelera ao chegar no conteúdo.
            eased_progress = 1 - (1 - progress) ** 2
            width = round(current_width + (target_width - current_width) * eased_progress)
            height = round(current_height + (target_height - current_height) * eased_progress)
            self.root.geometry(f"{width}x{height}")

            if step < WINDOW_RESIZE_STEPS:
                self.resize_animation = self.root.after(
                    WINDOW_RESIZE_INTERVAL_MS, lambda: animate(step + 1)
                )
            else:
                self.resize_animation = None

        animate()

    def btn(self, parent, text, command, width=None, height=None, *, variant="secondary", **pack_kw):
        palette = {
            "primary": (ACCENT, ACCENT_HOVER, ACCENT_TEXT),
            "danger": (DANGER, DANGER_HOVER, FG),
            "warning": (BG, SURFACE_ELEVATED, WARNING),
            "ghost": (SURFACE, SURFACE_ELEVATED, FG_MUTED),
            "secondary": (BG_BTN, BG_HOVER, FG),
        }
        normal_bg, hover_bg, foreground = palette.get(variant, palette["secondary"])
        b = RoundedButton(
            parent,
            text,
            command,
            normal_bg,
            hover_bg,
            foreground,
            width=width,
            height=height,
        )
        if pack_kw:
            b.pack(**pack_kw)
        return b

    def label_img(self, parent, photo, on_click):
        lbl = tk.Label(
            parent,
            image=photo,
            cursor="hand2",
            bd=0,
            bg=parent.cget("bg"),
            highlightthickness=0,
        )
        lbl.image = photo
        lbl.bind("<Button-1>", lambda e: on_click())
        return lbl

    def pill(self, parent, text: str, color: str, *, bg=None):
        return tk.Label(
            parent,
            text=text,
            bg=bg or parent.cget("bg"),
            fg=color,
            font=("Arial", 7, "bold"),
            padx=0,
            pady=0,
        )

    def bind_card_action(self, card, command, *widgets):
        """Clique e hover uniformes para cartões da tela inicial."""
        all_widgets = (card, *widgets)

        def enter(_event):
            card.configure(bg=CARD_HOVER)
            try:
                card.configure(highlightbackground="#53658D")
            except tk.TclError:
                pass
            for widget in widgets:
                try:
                    widget.configure(bg=CARD_HOVER)
                except tk.TclError:
                    pass

        def leave(_event):
            card.configure(bg=CARD)
            try:
                card.configure(highlightbackground=BORDER)
            except tk.TclError:
                pass
            for widget in widgets:
                try:
                    widget.configure(bg=CARD)
                except tk.TclError:
                    pass

        for widget in all_widgets:
            widget.configure(cursor="hand2")
            widget.bind("<Enter>", enter)
            widget.bind("<Leave>", leave)
            widget.bind("<ButtonRelease-1>", lambda _event: command())

    def _bind_icon_action(self, item, command, icon, title, underline):
        """Interação de ícones sem caixas e sem oscilar ao cruzar seus filhos."""
        widgets = (item, icon, title, underline)
        hover_job = None
        normal_bg = item.cget("bg")

        def refresh_hover():
            nonlocal hover_job
            hover_job = None
            target = self.root.winfo_containing(
                self.root.winfo_pointerx(), self.root.winfo_pointery()
            )
            is_inside = target is not None and str(target).startswith(str(item))
            hover_bg = CARD_HOVER if is_inside else normal_bg
            item.configure(bg=hover_bg)
            try:
                item.configure(highlightbackground=ACCENT if is_inside else BORDER)
            except tk.TclError:
                pass
            for widget in widgets[1:]:
                try:
                    widget.configure(bg=hover_bg)
                except tk.TclError:
                    pass
            title.configure(fg=FG if is_inside else FG_MUTED)
            underline.configure(bg=ACCENT if is_inside else normal_bg)

        def schedule_hover(_event=None):
            nonlocal hover_job
            if hover_job is None:
                hover_job = item.after_idle(refresh_hover)

        for widget in widgets:
            widget.configure(cursor="hand2")
            widget.bind("<Enter>", schedule_hover)
            widget.bind("<Leave>", schedule_hover)
            widget.bind("<ButtonRelease-1>", lambda _event: command())

    def _bind_account_hover(self, item, icon, title, underline):
        """Destaca contas pelo nome, sem reintroduzir cartões ou tabelas."""
        widgets = (item, icon, title, underline)
        hover_job = None
        normal_bg = item.cget("bg")

        def refresh_hover():
            nonlocal hover_job
            hover_job = None
            target = self.root.winfo_containing(
                self.root.winfo_pointerx(), self.root.winfo_pointery()
            )
            is_inside = target is not None and str(target).startswith(str(item))
            hover_bg = CARD_HOVER if is_inside else normal_bg
            item.configure(bg=hover_bg)
            try:
                item.configure(highlightbackground=ACCENT if is_inside else BORDER)
            except tk.TclError:
                pass
            icon.configure(bg=hover_bg)
            title.configure(bg=hover_bg, fg=FG if is_inside else FG_MUTED)
            underline.configure(bg=ACCENT if is_inside else normal_bg)

        def schedule_hover(_event=None):
            nonlocal hover_job
            if hover_job is None:
                hover_job = item.after_idle(refresh_hover)

        for widget in widgets:
            widget.configure(cursor="hand2")
            widget.bind("<Enter>", schedule_hover, add="+")
            widget.bind("<Leave>", schedule_hover, add="+")

    def get_image(self, path: Path, size: tuple):
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
            photo = ImageTk.PhotoImage(img)
            self.image_cache[key] = photo
            return photo
        except Exception as e:
            print(f"Erro ao carregar {path}: {e}")
            return None

    def icon_path(self, kind: str, platform: str, status: str) -> Path:
        """kind: 'platforms' | 'accounts' — status A → .png, B → .webp"""
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
        if self.current_platform:
            return PLATFORM_COLUMNS.get(self.current_platform, COLS)
        return COLS

    def _account_grid_options(self, index: int) -> dict:
        cols = self.grid_columns()
        row, col = divmod(index, cols)
        return {
            "row": row,
            "column": col,
            "padx": (0 if col == 0 else GRID_CARD_PAD_X, 0 if col == cols - 1 else GRID_CARD_PAD_X),
            "pady": (0 if row == 0 else GRID_CARD_PAD_Y, GRID_CARD_PAD_Y),
        }

    def context_menu(self, profile_name: str) -> tk.Menu:
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=SURFACE_ELEVATED,
            fg=FG,
            activebackground=ACCENT,
            activeforeground=FG,
            bd=1,
            relief=tk.FLAT,
        )
        menu.add_command(label="Editar", command=lambda: self.edit_profile(profile_name))
        menu.add_command(label="Clonar", command=lambda: self.clone_profile(profile_name))
        menu.add_command(label="Limpeza pesada", command=lambda: self.heavy_clean_profile(profile_name))
        menu.add_command(label="Excluir", command=lambda: self.delete_profile(profile_name))
        return menu

    def bind_context_menu(self, menu: tk.Menu, *widgets):
        """Abre o menu sem executar uma opção ao soltar o botão direito."""
        def show(event):
            if self.open_context_menu is not None:
                self.open_context_menu.unpost()

            # tk_popup captura o mouse e pode selecionar a primeira opção ao
            # soltar o botão direito. post só exibe o menu; Editar ou Excluir
            # exigem um clique explícito do usuário.
            menu.post(event.x_root, event.y_root)
            self.open_context_menu = menu
            return "break"

        for widget in widgets:
            widget.bind("<ButtonPress-3>", show)

    # ── backup e restauração ─────────────────────────────────

    def _navehub_dir(self) -> Path:
        return self.launcher.base_dir.parent

    def _config_file(self) -> Path:
        return self._navehub_dir() / "config.json"

    def _running_profile_dirs(self) -> list[Path]:
        running = []
        platform_dirs = (
            self.launcher.base_dir.iterdir()
            if self.launcher.base_dir.exists()
            else []
        )
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
            "version": 2,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "contents": ["config.json", "platforms"],
        }

    def create_backup(self):
        if not self._ensure_accounts_closed("Backup"):
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = filedialog.asksaveasfilename(
            parent=self.root,
            title="Salvar backup do NaveHub",
            initialfile=f"navehub-backup-{timestamp}.tar.gz",
            defaultextension=".tar.gz",
            filetypes=[
                ("Backup completo do NaveHub", "*.tar.gz"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not filename:
            return
        try:
            target = Path(filename)
            manifest_bytes = json.dumps(
                self._backup_manifest(),
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8")
            with tarfile.open(target, "w:gz", dereference=False) as backup:
                manifest_info = tarfile.TarInfo("manifest.json")
                manifest_info.size = len(manifest_bytes)
                manifest_info.mtime = datetime.now().timestamp()
                backup.addfile(manifest_info, io.BytesIO(manifest_bytes))

                config_file = self._config_file()
                if config_file.exists():
                    backup.add(config_file, arcname="config.json", recursive=False)

                platforms_dir = self.launcher.base_dir
                platforms_dir.mkdir(parents=True, exist_ok=True)
                backup.add(platforms_dir, arcname="platforms", recursive=True)
            try:
                target.chmod(0o600)
            except OSError:
                pass
        except (OSError, tarfile.TarError) as error:
            self.show_error("Backup", f"Não foi possível criar o backup.\n\n{error}")
            return
        self.show_info("Backup criado", f"Backup completo salvo em:\n{target}")

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
                raise ValueError("O backup contém arquivos especiais não suportados.")
            if member.issym():
                link_name = Path(member.linkname)
                if link_name.is_absolute():
                    raise ValueError("O backup contém links inválidos.")
                link_target = (target.parent / link_name).resolve()
                if link_target != destination and destination not in link_target.parents:
                    raise ValueError("O backup contém links inválidos.")
                symlink_paths.add(target)

        for member in members:
            target = (destination / member.name).resolve()
            if any(parent in symlink_paths for parent in target.parents):
                raise ValueError("O backup contém caminhos dentro de links.")

        backup.extractall(destination)

    def _extract_and_validate_backup(self, filename: Path, destination: Path):
        try:
            with tarfile.open(filename, "r:gz") as backup:
                self._safe_extract_tar(backup, destination)
        except tarfile.TarError as error:
            raise ValueError("O arquivo selecionado não é um backup completo válido.") from error

        manifest_file = destination / "manifest.json"
        platforms_dir = destination / "platforms"
        config_file = destination / "config.json"

        if not manifest_file.is_file():
            raise ValueError("O backup não contém manifest.json.")
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("O manifest do backup está inválido.") from error
        if manifest.get("format") != "NaveHub Backup" or manifest.get("version") != 2:
            raise ValueError("Este backup não é compatível com a restauração completa.")
        if not platforms_dir.is_dir():
            raise ValueError("O backup não contém o diretório completo de contas.")
        if config_file.exists():
            try:
                json.loads(config_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError("O config.json do backup está inválido.") from error

    def _replace_path_from_backup(self, source: Path, target: Path, rollback_root: Path):
        rollback = rollback_root / target.name
        if target.exists() or target.is_symlink():
            shutil.move(str(target), str(rollback))
        try:
            if source.exists() or source.is_symlink():
                shutil.move(str(source), str(target))
        except OSError:
            if target.exists() or target.is_symlink():
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            if rollback.exists() or rollback.is_symlink():
                shutil.move(str(rollback), str(target))
            raise

    def _apply_complete_backup(self, extracted_dir: Path):
        navehub_dir = self._navehub_dir()
        navehub_dir.mkdir(parents=True, exist_ok=True)
        rollback_root = Path(tempfile.mkdtemp(prefix="navehub-rollback-", dir=navehub_dir))
        try:
            self._replace_path_from_backup(
                extracted_dir / "platforms",
                self.launcher.base_dir,
                rollback_root,
            )
            config_source = extracted_dir / "config.json"
            if config_source.exists():
                self._replace_path_from_backup(config_source, self._config_file(), rollback_root)
            elif self._config_file().exists():
                shutil.move(str(self._config_file()), str(rollback_root / "config.json"))

            if self._config_file().exists():
                self.config.clear()
                self.config.update(
                    json.loads(self._config_file().read_text(encoding="utf-8"))
                )
            self.launcher.base_dir.mkdir(parents=True, exist_ok=True)
            self.launcher._initialization_marker = self.launcher.base_dir / ".navehub_initialized"
            self.launcher._initialization_marker.touch(exist_ok=True)
        except Exception:
            for name in ("platforms", "config.json"):
                target = navehub_dir / name
                rollback = rollback_root / name
                if target.exists() or target.is_symlink():
                    if target.is_dir() and not target.is_symlink():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                if rollback.exists() or rollback.is_symlink():
                    shutil.move(str(rollback), str(target))
            raise
        finally:
            shutil.rmtree(rollback_root, ignore_errors=True)

    def restore_backup(self):
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Restaurar backup do NaveHub",
            filetypes=[
                ("Backup completo do NaveHub", "*.tar.gz"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not filename:
            return

        if not self.ask_yes_no(
            "Substituir dados atuais?",
            "A restauração substituirá o estado atual do NaveHub pelo estado salvo "
            "no backup selecionado.\n\n"
            "- Os dados atuais serão substituídos.\n"
            "- Contas que não existem no backup serão removidas.\n"
            "- Contas existentes no backup voltarão exatamente ao estado salvo.\n\n"
            "Feche todas as janelas de contas antes de continuar. O backup original "
            "não será apagado nem modificado.\n\nContinuar?",
        ):
            return

        if not self._ensure_accounts_closed("Restaurar backup"):
            return

        restore_temp = Path(tempfile.mkdtemp(prefix="navehub-restore-"))
        try:
            self._extract_and_validate_backup(Path(filename), restore_temp)
            self._apply_complete_backup(restore_temp)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.show_error(
                "Restaurar backup",
                f"Não foi possível concluir a restauração.\n\n{error}",
            )
            return
        finally:
            shutil.rmtree(restore_temp, ignore_errors=True)

        self.image_cache.clear()
        self.show_platform_menu()
        self.show_info("Restaurado", "O NaveHub foi restaurado exatamente para o estado do backup.")

    # ── home ─────────────────────────────────────────────────

    def show_platform_menu(self):
        self.clear_frame()
        self.current_platform = None
        self.profiles_canvas = None
        self.root.title("NaveHub")

        screen = tk.Frame(self.main_frame, bg=BG)
        screen.pack(fill=tk.BOTH, expand=True, padx=WINDOW_CONTENT_MARGIN, pady=WINDOW_CONTENT_MARGIN)

        frame = tk.Frame(screen, bg=BG)
        frame.pack(expand=True)

        for index, name in enumerate(PLATFORMS):
            status = self.launcher.get_platform_status(name)
            photo = self.get_image(self.icon_path("platforms", name, status), PLATFORM_ICON)
            item = tk.Frame(frame, bg=BG, width=280, height=78)
            item.grid(row=index, column=0, padx=0, pady=(0, 4))
            item.grid_propagate(False)

            if photo:
                action = tk.Label(item, image=photo, bg=BG, bd=0)
                action.image = photo
                action.pack(pady=(0, 0))
            else:
                action = tk.Label(
                    item,
                    text=name,
                    bg=BG,
                    fg=FG,
                    font=("Arial", 12, "bold"),
                    height=2,
                )
                action.pack(expand=True)

            underline = tk.Frame(item, bg=BG, height=1, width=18)
            underline.pack(pady=(1, 0))
            self._bind_icon_action(
                item,
                lambda p=name: self.show_platform(p),
                action,
                action,
                underline,
            )

        footer = tk.Frame(screen, bg=BG)
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 0))
        footer_inner = tk.Frame(footer, bg=BG)
        footer_inner.pack(anchor="center")
        self.btn(
            footer_inner,
            "Backup",
            self.create_backup,
            variant="secondary",
            side=tk.LEFT,
            padx=(0, 6),
        )
        self.btn(
            footer_inner,
            "Restaurar",
            self.restore_backup,
            variant="ghost",
            side=tk.LEFT,
            padx=(0, 6),
        )
        self.fit_window_to_content()

    def update_static_platform_favicons(self):
        def complete(result):
            self.root.after(0, lambda: self._finish_static_favicon_update(result))

        started = self.launcher.enqueue_static_platform_favicons(
            force=True,
            on_complete=complete,
        )
        if not started:
            self.show_warning(
                "Favicons em andamento",
                "Já existe uma atualização de Favicons em processamento.",
            )

    def _finish_static_favicon_update(self, result: dict):
        self.image_cache.clear()
        if self.current_platform == STATIC_PLATFORM:
            self.load_profiles()
        self.show_info(
            "Favicons atualizados",
            "Sincronização concluída para Legalizadas.\n\n"
            f"Atualizados: {result['updated']}\n"
            f"Sem URL válida: {result['skipped']}\n"
            f"Falhas: {result['failed']}",
        )

    # ── contas ───────────────────────────────────────────────

    def show_platform(self, platform_name: str):
        # Carrega os bitmaps enquanto a tela atual ainda está visível. Isso
        # evita o quadro preto/"piscada" entre limpar o menu e montar a grade.
        profiles = self.launcher.list_profiles(platform_name)
        self.preload_profile_icons(platform_name, profiles)

        self.clear_frame()
        self.current_platform = platform_name
        self._profile_order = profiles[:]
        self.root.title("NaveHub")

        screen = tk.Frame(self.main_frame, bg=BG)
        screen.pack(
            fill=tk.BOTH,
            expand=True,
            padx=WINDOW_CONTENT_MARGIN,
            pady=WINDOW_CONTENT_MARGIN,
        )

        top = tk.Frame(
            screen,
            bg=BG,
        )
        top.pack(fill=tk.X, pady=(0, 8))
        toolbar = tk.Frame(top, bg=BG)
        toolbar.pack(fill=tk.X)
        self.btn(
            toolbar,
            "←  Plataformas",
            self.show_platform_menu,
            variant="ghost",
            side=tk.LEFT,
        )

        if platform_name != STATIC_PLATFORM:
            self.btn(
                toolbar,
                "↺  Resetar",
                self.reset_platform_statuses,
                variant="warning",
                side=tk.RIGHT,
            )

        container = tk.Frame(screen, bg=BG)
        container.pack(fill=tk.BOTH, expand=True)
        if platform_name == STATIC_PLATFORM:
            self.profiles_canvas = tk.Canvas(
                container,
                bg=BG,
                bd=0,
                highlightthickness=0,
                xscrollincrement=1,
                yscrollincrement=20,
            )
            self.profiles_canvas.pack(anchor="n")
            self.profiles_frame = tk.Frame(self.profiles_canvas, bg=BG)
            self.profiles_frame.grid_anchor("center")
            self.profiles_canvas.create_window((0, 0), window=self.profiles_frame, anchor="nw")
            self._bind_profiles_canvas_scroll()
        else:
            self.profiles_canvas = None
            self.profiles_frame = tk.Frame(container, bg=BG)
            self.profiles_frame.grid_anchor("center")
            self.profiles_frame.pack(anchor="n", fill=tk.BOTH, expand=True)

        actions = tk.Frame(screen, bg=BG)
        actions.pack(fill=tk.X, pady=(8, 0))
        if platform_name == STATIC_PLATFORM:
            self.btn(
                actions,
                "Atualizar Favicons",
                self.update_static_platform_favicons,
                variant="secondary",
                side=tk.LEFT,
            )
        self.btn(
            actions,
            "＋  Nova conta",
            self.add_new_profile,
            variant="primary",
            side=tk.RIGHT,
        )

        self.load_profiles(profiles)
        if platform_name == STATIC_PLATFORM:
            self.enqueue_missing_static_favicons(profiles)

    def preload_profile_icons(self, platform: str, profiles: list[str]):
        """Mantém no cache os ícones que serão exibidos na próxima grade."""
        paths = {
            self.account_icon_path(
                platform,
                profile_name,
                self.launcher.get_profile_status(platform, profile_name),
            )
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
            if remaining > 0:
                return
            self.root.after(0, self._refresh_static_favicon_icons)

        for profile_name in missing:
            if not self.launcher.enqueue_static_profile_favicon(
                profile_name,
                on_complete=complete,
            ):
                remaining -= 1
        if remaining == 0:
            self._refresh_static_favicon_icons()

    def _refresh_static_favicon_icons(self):
        if self.current_platform != STATIC_PLATFORM:
            return
        self.image_cache.clear()
        self.load_profiles()

    def load_profiles(self, profiles: list[str] | None = None):
        for w in self.profiles_frame.winfo_children():
            w.destroy()

        if profiles is None:
            profiles = self.launcher.list_profiles(self.current_platform)
        self._profile_order = profiles[:]
        self._account_items = {}
        self._account_widgets = {}
        if not profiles:
            tk.Label(
                self.profiles_frame,
                text="Nenhuma conta nesta plataforma",
                fg=FG_MUTED,
                bg=BG,
                font=("Arial", 10),
            ).pack(pady=40)
            self._update_profiles_canvas_region()
            self.fit_window_to_content()
            return

        safe_platform = self.current_platform

        for index, name in enumerate(profiles):
            status = self.launcher.get_profile_status(safe_platform, name)
            display = self.launcher.get_profile_display_name(safe_platform, name)
            item = tk.Frame(self.profiles_frame, bg=BG, width=ACCOUNT_CARD_WIDTH, height=ACCOUNT_CARD_HEIGHT)
            item.grid_propagate(False)
            item.grid(**self._account_grid_options(index))

            icon_path = self.account_icon_path(safe_platform, name, status)
            photo = self.get_image(icon_path, ACCOUNT_ICON)
            if photo:
                account_button = tk.Label(
                    item,
                    image=photo,
                    cursor="hand2",
                    bd=0,
                    bg=BG,
                    highlightthickness=0,
                )
                cast(Any, account_button).image = photo
                cast(Any, item).image = photo
                account_button.pack(pady=(0, 0))
            else:
                account_button = tk.Label(
                    item,
                    text=f"{display}\n[{status}]",
                    width=10,
                    height=3,
                    cursor="hand2",
                    bg=BG,
                    fg=FG,
                    font=("Arial", 9),
                )
                account_button.pack(pady=(0, 0))

            account_name = tk.Label(
                item,
                text=display,
                font=("Arial", 8),
                wraplength=ACCOUNT_ICON[0],
                bg=BG,
                fg=FG_MUTED,
            )
            account_name.pack(pady=(1, 0))
            underline = tk.Frame(item, bg=BG, height=1, width=16)
            underline.pack(pady=(1, 0))

            menu = self.context_menu(name)
            self.bind_context_menu(menu, item, account_button, account_name, underline)
            self._bind_account_drag(name, item, account_button, account_name, underline)
            self._account_items[name] = item
            self._account_widgets[name] = (account_button, account_name)

            self._bind_account_hover(item, account_button, account_name, underline)

        self._update_profiles_canvas_region()
        self.fit_window_to_content()

    def _bind_profiles_canvas_scroll(self):
        if self.profiles_canvas is None:
            return

        def scroll(event):
            if event.num == 4:
                delta = -1
            elif event.num == 5:
                delta = 1
            else:
                delta = -1 if event.delta > 0 else 1
            self.profiles_canvas.yview_scroll(delta, "units")
            return "break"

        def bind_wheel(_event):
            self.root.bind_all("<MouseWheel>", scroll)
            self.root.bind_all("<Button-4>", scroll)
            self.root.bind_all("<Button-5>", scroll)

        def unbind_wheel(_event):
            self.root.unbind_all("<MouseWheel>")
            self.root.unbind_all("<Button-4>")
            self.root.unbind_all("<Button-5>")

        self.profiles_canvas.bind("<Enter>", bind_wheel)
        self.profiles_canvas.bind("<Leave>", unbind_wheel)

    def _update_profiles_canvas_region(self):
        if self.profiles_canvas is None:
            return
        self.profiles_frame.update_idletasks()
        width = max(1, self.profiles_frame.winfo_reqwidth())
        height = max(1, self.profiles_frame.winfo_reqheight())
        visible_height = min(height, max(ACCOUNT_CARD_HEIGHT, self.root.winfo_screenheight() - 220))
        self.profiles_canvas.configure(
            width=width,
            height=visible_height,
            scrollregion=(0, 0, width, height),
        )

    # ── arrastar contas (estilo Android) ─────────────────────

    def _bind_account_drag(self, profile_name: str, *widgets):
        """Clique abre; segurar ou mover o ícone reorganiza a grade."""
        for widget in widgets:
            widget.bind(
                "<ButtonPress-1>",
                lambda event, name=profile_name: self._account_press(event, name),
            )
            widget.bind("<B1-Motion>", self._account_motion)
            widget.bind(
                "<ButtonRelease-1>",
                lambda event, name=profile_name: self._account_release(event, name),
            )

    def _account_press(self, event, profile_name: str):
        self._cancel_drag_hold()
        try:
            event.widget.grab_set()
        except tk.TclError:
            pass
        self._drag_state = {
            "source": profile_name,
            "x": event.x_root,
            "y": event.y_root,
            "dragging": False,
        }
        self._drag_after = self.root.after(DRAG_HOLD_MS, self._start_account_drag)
        return "break"

    def _cancel_drag_hold(self):
        if self._drag_after is not None:
            try:
                self.root.after_cancel(self._drag_after)
            except tk.TclError:
                pass
            self._drag_after = None

    def _start_account_drag(self):
        self._drag_after = None
        state = self._drag_state
        if not state or state["dragging"]:
            return
        state["dragging"] = True
        self.root.configure(cursor="fleur")
        state["original_order"] = self._profile_order[:]
        state["order"] = self._profile_order[:]
        self._account_items[state["source"]].grid_remove()
        state["placeholder"] = tk.Frame(
            self.profiles_frame,
            bg=SURFACE_ELEVATED,
            width=ACCOUNT_CARD_WIDTH,
            height=ACCOUNT_CARD_HEIGHT,
            highlightbackground="#53658D",
            highlightthickness=1,
        )
        state["placeholder"].grid_propagate(False)
        state["ghost"] = self._create_drag_ghost(state["source"])
        self._layout_drag_order(state)
        self._move_drag_ghost(state["x"], state["y"])

    def _account_motion(self, event):
        state = self._drag_state
        if not state:
            return "break"
        if not state["dragging"]:
            distance = abs(event.x_root - state["x"]) + abs(event.y_root - state["y"])
            if distance >= DRAG_THRESHOLD:
                self._start_account_drag()
        if state["dragging"]:
            self._move_drag_ghost(event.x_root, event.y_root)
            self._move_drag_to_pointer(event.x_root, event.y_root)
        return "break"

    def _create_drag_ghost(self, profile_name: str):
        """Cópia flutuante do cartão, como o ícone arrastado no Android."""
        account_button, account_name = self._account_widgets[profile_name]
        ghost = tk.Frame(
            self.root,
            bg=SURFACE_ELEVATED,
            highlightthickness=0,
            bd=0,
        )
        image_name = account_button.cget("image")
        if image_name:
            icon = tk.Label(ghost, image=image_name, bg=SURFACE_ELEVATED, bd=0)
            cast(Any, icon).image = account_button.image
        else:
            icon = tk.Label(
                ghost,
                text=account_button.cget("text"),
                bg=SURFACE_ELEVATED,
                fg=FG,
                font=("Arial", 10),
            )
        icon.pack(padx=4, pady=(4, 1))
        tk.Label(
            ghost,
            text=account_name.cget("text"),
            bg=SURFACE_ELEVATED,
            fg=FG,
            font=("Arial", 8),
        ).pack(padx=4, pady=(0, 4))
        ghost.update_idletasks()
        return ghost

    def _move_drag_ghost(self, x_root: int, y_root: int):
        state = self._drag_state
        if not state or not state.get("ghost"):
            return
        ghost = state["ghost"]
        ghost.place(
            x=x_root - self.root.winfo_rootx(),
            y=y_root - self.root.winfo_rooty(),
            anchor="center",
        )
        ghost.lift()

    def _drag_slot_at(self, x_root: int, y_root: int):
        state = self._drag_state
        if not state:
            return None
        closest_index = None
        closest_distance = float("inf")
        source = state["source"]
        for index, name in enumerate(state["order"]):
            widget = state["placeholder"] if name == source else self._account_items[name]
            center_x = widget.winfo_rootx() + widget.winfo_width() / 2
            center_y = widget.winfo_rooty() + widget.winfo_height() / 2
            distance = (center_x - x_root) ** 2 + (center_y - y_root) ** 2
            if distance < closest_distance:
                closest_index = index
                closest_distance = distance
        return closest_index

    def _move_drag_to_pointer(self, x_root: int, y_root: int):
        state = self._drag_state
        slot = self._drag_slot_at(x_root, y_root)
        if not state or slot is None:
            return
        order = state["order"]
        source_index = order.index(state["source"])
        if source_index == slot:
            return
        order.pop(source_index)
        order.insert(slot, state["source"])
        self._layout_drag_order(state)

    def _layout_drag_order(self, state):
        source = state["source"]
        for index, name in enumerate(state["order"]):
            widget = state["placeholder"] if name == source else self._account_items[name]
            widget.grid(**self._account_grid_options(index))

    def _layout_profile_order(self, order: list[str]):
        for index, name in enumerate(order):
            self._account_items[name].grid(**self._account_grid_options(index))

    def _account_release(self, event, profile_name: str):
        self._cancel_drag_hold()
        state = self._drag_state
        self._drag_state = None
        try:
            event.widget.grab_release()
        except tk.TclError:
            pass
        self.root.configure(cursor="")

        if not state or state["source"] != profile_name:
            return "break"
        if not state["dragging"]:
            self.open_profile(profile_name)
            return "break"

        state["ghost"].destroy()
        state["placeholder"].destroy()
        order = state["order"]
        self._profile_order = order[:]
        self._layout_profile_order(order)
        if order != state["original_order"]:
            self.launcher.save_profile_order(self.current_platform, order)
        return "break"


    # ── ações ────────────────────────────────────────────────

    def open_profile(self, profile_name: str):
        if self.launcher.launch_profile(self.current_platform, profile_name):
            self.load_profiles()  # só atualiza status, sem remontar a tela
        else:
            self.show_error(
                "Erro",
                f"Navegador '{self.config.get('browser')}' não encontrado.",
            )

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
        self.show_info(
            "Status resetado",
            f"{changed} conta(s) voltaram ao status B.",
        )

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
        """Diálogo unificado criar / editar."""
        is_edit = mode == "edit"
        win = tk.Toplevel(self.root)
        win.title("NaveHub")
        win.geometry("420x315")
        win.configure(bg=SURFACE)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        header = tk.Frame(win, bg=SURFACE)
        header.pack(fill=tk.X, padx=18, pady=(16, 6))
        tk.Label(
            header,
            text="Editar conta" if is_edit else "Nova conta",
            bg=SURFACE,
            fg=FG,
            font=("Arial", 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Defina como esta conta aparecerá no NaveHub.",
            bg=SURFACE,
            fg=FG_MUTED,
            font=("Arial", 9),
        ).pack(anchor="w", pady=(3, 0))

        def field(text, value=""):
            tk.Label(win, text=text, bg=SURFACE, fg=FG_MUTED, font=("Arial", 9, "bold")).pack(
                anchor="w", padx=18, pady=(10, 5) if text.startswith("Nome") else (8, 5)
            )
            e = tk.Entry(
                win,
                width=35,
                bg=CARD,
                fg=FG,
                insertbackground=FG,
                relief=tk.FLAT,
                highlightthickness=1,
                highlightbackground=BORDER,
                highlightcolor=ACCENT,
                font=("Arial", 10),
            )
            if value:
                e.insert(0, value)
            e.pack(fill=tk.X, padx=18, ipady=6)
            return e

        current_display = (
            self.launcher.get_profile_display_name(self.current_platform, profile_name) if is_edit else ""
        )
        current_site = (
            self.launcher.get_profile_homepage(self.current_platform, profile_name)
            if is_edit
            else self.launcher.get_default_homepage(self.current_platform) or self.config.get("homepage", "https://site.com")
        )

        name_entry = field("Nome da conta:", current_display)
        site_entry = field("Site da conta:", current_site)
        if not is_edit:
            name_entry.focus()

        def save():
            name = name_entry.get().strip()
            site = site_entry.get().strip()
            if is_edit:
                if not name or not site:
                    self.show_warning("Aviso", "Nome e site são obrigatórios.")
                    return
                target = profile_name
                if name != current_display:
                    if not self.launcher.rename_profile(
                        self.current_platform, profile_name, name
                    ):
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
            win.destroy()

        actions = tk.Frame(win, bg=SURFACE)
        actions.pack(fill=tk.X, padx=18, pady=12)
        self.btn(
            actions,
            "Salvar" if is_edit else "Criar",
            save,
            variant="primary",
            side=tk.LEFT,
            padx=(0, 6),
        )
        self.btn(actions, "Cancelar", win.destroy, variant="ghost", side=tk.LEFT)

    def run(self):
        self.root.mainloop()
