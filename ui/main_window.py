import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog
import json
import shutil
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageTk
from launcher.profile_launcher import ProfileLauncher, STATIC_PLATFORM


BG = "#080C14"
SURFACE = "#0D131E"
SURFACE_ELEVATED = "#141D2B"
CARD = "#101824"
CARD_HOVER = "#182337"
BG_BTN = "#172132"
BG_HOVER = "#22314A"
FG = "#F5F7FC"
FG_MUTED = "#94A1B6"
BORDER = "#243148"
ACCENT = "#8B9CFF"
ACCENT_HOVER = "#AAB6FF"
ACCENT_TEXT = "#0A1020"
SUCCESS = "#34D399"
WARNING = "#FBBF24"
DANGER = "#FB7185"
DANGER_HOVER = "#E85D75"

PLATFORMS = ("8U", "777", "365GG", "93H", STATIC_PLATFORM)
PLATFORM_ICON = (300, 98)
ACCOUNT_ICON = (70, 70)
COLS = 4
WINDOW_MIN_WIDTH = 420
WINDOW_MIN_HEIGHT = 748
WINDOW_ASPECT_RATIO = 9 / 16
WINDOW_SCREEN_MARGIN = 80
WINDOW_RESIZE_STEPS = 10
WINDOW_RESIZE_INTERVAL_MS = 16
DRAG_HOLD_MS = 220
DRAG_THRESHOLD = 8
ACCOUNT_CARD_WIDTH = 88
ACCOUNT_CARD_HEIGHT = 104


class RoundedButton(tk.Canvas):
    """Botão leve com cantos arredondados, independente do tema do sistema."""

    def __init__(self, parent, text, command, normal_bg, hover_bg, foreground,
                 width=None, height=None):
        self.text = text
        self.command = command
        self.normal_bg = normal_bg
        self.hover_bg = hover_bg
        self.foreground = foreground
        self.radius = 10
        self.font = ("Arial", 9, "bold")
        measure = tkfont.Font(font=self.font)
        calculated_width = measure.measure(text) + 30
        if width is not None:
            calculated_width = max(calculated_width, width * 8 + 18)
        self.button_width = calculated_width
        self.button_height = height or 36
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
        frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=22)

        accent = {"info": ACCENT, "warning": WARNING, "error": DANGER}.get(kind, ACCENT)
        title_row = tk.Frame(frame, bg=SURFACE)
        title_row.pack(fill=tk.X, anchor="w")
        tk.Label(title_row, text=title, bg=SURFACE, fg=FG, font=("Arial", 13, "bold")).pack(anchor="w")
        tk.Label(frame, text=message, bg=SURFACE, fg=FG_MUTED, font=("Arial", 10), justify="left", wraplength=width - 48).pack(anchor="w", pady=(10, 18))

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
        btn.pack(side=tk.RIGHT, padx=(8, 0))

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

        base = Path(__file__).parent.parent
        self.icons_platforms = base / "icons" / "platforms"
        self.icons_accounts = base / "icons" / "accounts"
        self.icons_platforms.mkdir(parents=True, exist_ok=True)
        self.icons_accounts.mkdir(parents=True, exist_ok=True)

        # className=NaveHub → WM_CLASS bate com StartupWMClass do .desktop (dock não duplica ícone)
        self.root = tk.Tk(className="NaveHub")
        self.root.title("NaveHub")
        self.root.geometry(f"{WINDOW_MIN_WIDTH}x{WINDOW_MIN_HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
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
        """Ajusta a janela à tela exibida, sem ocupar espaço vazio.

        A largura e altura mínimas mantêm os controles confortáveis, e o limite
        da tela evita que a janela abra além da área visível. Após a janela ser
        exibida, a mudança de tamanho é animada para suavizar a troca de tela.
        """
        self.root.update_idletasks()

        max_width = max(1, self.root.winfo_screenwidth() - WINDOW_SCREEN_MARGIN)
        max_height = max(1, self.root.winfo_screenheight() - WINDOW_SCREEN_MARGIN)
        required_width = max(self.root.winfo_reqwidth(), WINDOW_MIN_WIDTH)
        required_height = max(self.root.winfo_reqheight(), WINDOW_MIN_HEIGHT)

        # Mantém a janela panorâmica, inclusive quando a grade de contas
        # cresce. O conteúdo define o menor lado e a outra dimensão acompanha.
        target_width = max(required_width, round(required_height * WINDOW_ASPECT_RATIO))
        target_height = round(target_width / WINDOW_ASPECT_RATIO)
        if target_width > max_width or target_height > max_height:
            scale = min(max_width / target_width, max_height / target_height)
            target_width = max(1, round(target_width * scale))
            target_height = max(1, round(target_height * scale))

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

        def refresh_hover():
            nonlocal hover_job
            hover_job = None
            target = self.root.winfo_containing(
                self.root.winfo_pointerx(), self.root.winfo_pointery()
            )
            is_inside = target is not None and str(target).startswith(str(item))
            title.configure(fg=ACCENT if is_inside else FG_MUTED)
            underline.configure(bg=ACCENT if is_inside else BG)

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

        def refresh_hover():
            nonlocal hover_job
            hover_job = None
            target = self.root.winfo_containing(
                self.root.winfo_pointerx(), self.root.winfo_pointery()
            )
            is_inside = target is not None and str(target).startswith(str(item))
            title.configure(fg=ACCENT if is_inside else FG_MUTED)
            underline.configure(bg=ACCENT if is_inside else BG)

        def schedule_hover(_event=None):
            nonlocal hover_job
            if hover_job is None:
                hover_job = item.after_idle(refresh_hover)

        for widget in widgets:
            widget.configure(cursor="hand2")
            widget.bind("<Enter>", schedule_hover, add="+")
            widget.bind("<Leave>", schedule_hover, add="+")

    def get_image(self, path: Path, size: tuple):
        key = (str(path), size)
        if key in self.image_cache:
            return self.image_cache[key]
        try:
            img = Image.open(path).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.image_cache[key] = photo
            return photo
        except Exception as e:
            print(f"Erro ao carregar {path}: {e}")
            return None

    def icon_path(self, kind: str, platform: str, status: str) -> Path:
        """kind: 'platforms' | 'accounts' — status A → .png, B → .webp"""
        # "Outras" usa ícones fixos e não participa do status diário A/B.
        if platform == STATIC_PLATFORM:
            folder = self.icons_platforms if kind == "platforms" else self.icons_accounts
            return folder / "outras.png"

        safe = platform.lower().replace(" ", "")
        folder = self.icons_platforms if kind == "platforms" else self.icons_accounts
        ext = "png" if status == "A" else "webp"
        return folder / f"{safe}_{status.lower()}.{ext}"

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

    @staticmethod
    def _profile_storage_key(profile_name: str) -> str:
        return "".join(
            char if char.isalnum() or char in "-_" else "_"
            for char in profile_name.lower()
        )

    def _backup_document(self) -> dict:
        """Serializa apenas as configurações do NaveHub, nunca cookies ou senhas."""
        platforms = {}
        for platform in PLATFORMS:
            profiles = []
            for profile_name in self.launcher.list_profiles(platform):
                profiles.append({
                    "name": profile_name,
                    "settings": self.launcher._read_profile_data(platform, profile_name),
                })
            platforms[platform] = {
                "profiles": profiles,
                "order": self.launcher._read_profile_order(platform),
            }
        return {
            "format": "NaveHub Backup",
            "version": 1,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "application": {"config": dict(self.config)},
            "platforms": platforms,
        }

    def create_backup(self):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = filedialog.asksaveasfilename(
            parent=self.root,
            title="Salvar backup do NaveHub",
            initialfile=f"navehub-backup-{timestamp}.json",
            defaultextension=".json",
            filetypes=[("Backup do NaveHub", "*.json")],
        )
        if not filename:
            return
        try:
            target = Path(filename)
            target.write_text(
                json.dumps(self._backup_document(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            try:
                target.chmod(0o600)
            except OSError:
                pass
        except OSError as error:
            self.show_error("Backup", f"Não foi possível criar o backup.\n\n{error}")
            return
        self.show_info("Backup criado", f"Configurações salvas em:\n{target}")

    def _validate_backup_document(self, document) -> dict:
        if not isinstance(document, dict):
            raise ValueError("O arquivo não contém um backup válido.")
        if document.get("format") != "NaveHub Backup" or document.get("version") != 1:
            raise ValueError("Este arquivo não é um backup compatível do NaveHub.")
        application = document.get("application")
        platforms = document.get("platforms")
        if not isinstance(application, dict) or not isinstance(application.get("config"), dict):
            raise ValueError("As configurações do aplicativo estão ausentes ou inválidas.")
        if not isinstance(platforms, dict):
            raise ValueError("As configurações das plataformas estão ausentes ou inválidas.")

        normalized = {"config": application["config"], "platforms": {}}
        for platform in PLATFORMS:
            source = platforms.get(platform, {"profiles": [], "order": []})
            if not isinstance(source, dict) or not isinstance(source.get("profiles"), list):
                raise ValueError(f"A plataforma {platform} está inválida.")

            profiles = []
            seen = set()
            for profile in source["profiles"]:
                if not isinstance(profile, dict):
                    raise ValueError(f"Uma conta de {platform} está inválida.")
                name = profile.get("name")
                settings = profile.get("settings")
                if not isinstance(name, str) or not name.strip() or not isinstance(settings, dict):
                    raise ValueError(f"Uma conta de {platform} está incompleta.")
                key = self._profile_storage_key(name)
                if key in seen:
                    raise ValueError(f"O backup tem contas duplicadas em {platform}.")
                seen.add(key)
                profiles.append({"name": name, "settings": settings})

            names_by_key = {
                self._profile_storage_key(item["name"]): item["name"]
                for item in profiles
            }
            source_order = source.get("order", [])
            if not isinstance(source_order, list) or not all(isinstance(name, str) for name in source_order):
                raise ValueError(f"A ordem das contas de {platform} está inválida.")
            order = []
            for name in source_order:
                actual = names_by_key.get(self._profile_storage_key(name))
                if actual and actual not in order:
                    order.append(actual)
            normalized["platforms"][platform] = {"profiles": profiles, "order": order}
        return normalized

    def _archive_profiles_not_in_backup(self, backup_platforms: dict):
        """Tira contas ausentes da configuração atual sem destruir suas sessões."""
        archive_root = (
            self.launcher.base_dir.parent
            / "restore_archive"
            / datetime.now().strftime("%Y%m%d-%H%M%S")
        )
        for platform in PLATFORMS:
            platform_dir = self.launcher.get_platform_dir(platform)
            expected = {
                self._profile_storage_key(item["name"])
                for item in backup_platforms[platform]["profiles"]
            }
            for profile_dir in list(platform_dir.iterdir()):
                if not profile_dir.is_dir() or profile_dir.name.lower() in expected:
                    continue
                destination = archive_root / platform.lower().replace(" ", "") / profile_dir.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(profile_dir), str(destination))

    def _apply_backup(self, backup: dict):
        self._archive_profiles_not_in_backup(backup["platforms"])
        for platform in PLATFORMS:
            platform_backup = backup["platforms"][platform]
            for profile in platform_backup["profiles"]:
                self.launcher._write_profile_data(platform, profile["name"], profile["settings"])
            self.launcher.save_profile_order(platform, platform_backup["order"])

        self.config.clear()
        self.config.update(backup["config"])
        config_file = Path.home() / ".navehub" / "config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps(self.config, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        marker = getattr(self.launcher, "_initialization_marker", None)
        if marker is not None:
            marker.touch(exist_ok=True)

    def restore_backup(self):
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Restaurar backup do NaveHub",
            filetypes=[("Backup do NaveHub", "*.json"), ("Todos os arquivos", "*.*")],
        )
        if not filename:
            return
        try:
            document = json.loads(Path(filename).read_text(encoding="utf-8"))
            backup = self._validate_backup_document(document)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            self.show_error("Restaurar backup", f"Backup inválido.\n\n{error}")
            return

        if not self.ask_yes_no(
            "Substituir configurações?",
            "A restauração substituirá completamente as contas, sites, status, "
            "ordem e configurações atuais pelos dados do backup.\n\n"
            "Contas ausentes no backup sairão do NaveHub e terão os dados locais "
            "arquivados em restore_archive. Continuar?",
        ):
            return
        try:
            self._apply_backup(backup)
        except OSError as error:
            self.show_error(
                "Restaurar backup",
                f"Não foi possível concluir a restauração.\n\n{error}",
            )
            return
        self.show_platform_menu()
        self.show_info("Restaurado", "As configurações foram substituídas pelo backup.")

    # ── home ─────────────────────────────────────────────────

    def show_platform_menu(self):
        self.clear_frame()
        self.current_platform = None
        self.root.title("NaveHub")

        screen = tk.Frame(self.main_frame, bg=BG)
        screen.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        frame = tk.Frame(screen, bg=BG)
        frame.pack(expand=True, pady=(0, 0))

        for index, name in enumerate(PLATFORMS):
            status = self.launcher.get_platform_status(name)
            photo = self.get_image(self.icon_path("platforms", name, status), PLATFORM_ICON)
            item = tk.Frame(
                frame,
                bg=BG,
                width=340,
                height=118,
            )
            item.grid(row=index, column=0, padx=0, pady=2)
            item.grid_propagate(False)

            if photo:
                action = tk.Label(item, image=photo, bg=BG, bd=0)
                action.image = photo
                action.pack(pady=(5, 1))
            else:
                action = tk.Label(
                    item,
                    text=name,
                    bg=BG,
                    fg=FG,
                    font=("Arial", 15, "bold"),
                    height=3,
                )
                action.pack(expand=True)

            underline = tk.Frame(item, bg=BG, height=2, width=26)
            underline.pack(pady=(6, 0))
            self._bind_icon_action(
                item,
                lambda p=name: self.show_platform(p),
                action,
                action,
                underline,
            )

        footer = tk.Frame(screen, bg=BG)
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
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
        )

        self.fit_window_to_content()

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
        screen.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        top = tk.Frame(
            screen,
            bg=BG,
        )
        top.pack(fill=tk.X, pady=(0, 10))
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
        self.profiles_frame = tk.Frame(container, bg=BG)
        self.profiles_frame.grid_anchor("center")
        self.profiles_frame.pack(anchor="n", pady=(2, 8))

        actions = tk.Frame(screen, bg=BG)
        actions.pack(fill=tk.X, pady=(10, 0))
        self.btn(
            actions,
            "＋  Nova conta",
            self.add_new_profile,
            variant="primary",
            side=tk.RIGHT,
        )

        self.load_profiles(profiles)

    def preload_profile_icons(self, platform: str, profiles: list[str]):
        """Mantém no cache os ícones que serão exibidos na próxima grade."""
        paths = {
            self.icon_path(
                "accounts",
                platform,
                self.launcher.get_profile_status(platform, profile_name),
            )
            for profile_name in profiles
        }
        for path in paths:
            self.get_image(path, ACCOUNT_ICON)

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
            self.fit_window_to_content()
            return

        safe_platform = self.current_platform
        col = row = 0

        for name in profiles:
            status = self.launcher.get_profile_status(safe_platform, name)
            display = self.launcher.get_display_name(name)
            item = tk.Frame(
                self.profiles_frame,
                bg=BG,
                width=ACCOUNT_CARD_WIDTH,
                height=ACCOUNT_CARD_HEIGHT,
            )
            item.grid_propagate(False)
            item.grid(row=row, column=col, padx=8, pady=8)

            photo = self.get_image(self.icon_path("accounts", safe_platform, status), ACCOUNT_ICON)
            if photo:
                account_button = tk.Label(
                    item,
                    image=photo,
                    cursor="hand2",
                    bd=0,
                    bg=BG,
                    highlightthickness=0,
                )
                account_button.image = photo
                account_button.pack(pady=(9, 0))
            else:
                account_button = tk.Label(
                    item,
                    text=f"{display}\n[{status}]",
                    width=12,
                    height=4,
                    cursor="hand2",
                    bg=BG,
                    fg=FG,
                    font=("Arial", 10),
                )
                account_button.pack(pady=(9, 0))

            account_name = tk.Label(
                item,
                text=display,
                font=("Arial", 8),
                wraplength=ACCOUNT_ICON[0],
                bg=BG,
                fg=FG_MUTED,
            )
            account_name.pack(pady=(4, 0))
            underline = tk.Frame(item, bg=BG, height=2, width=20)
            underline.pack(pady=(5, 0))

            menu = self.context_menu(name)
            self.bind_context_menu(menu, item, account_button, account_name, underline)
            self._bind_account_drag(name, item, account_button, account_name, underline)
            self._account_items[name] = item
            self._account_widgets[name] = (account_button, account_name)

            self._bind_account_hover(item, account_button, account_name, underline)

            col += 1
            if col >= COLS:
                col = 0
                row += 1

        self.fit_window_to_content()

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
            icon.image = account_button.image
        else:
            icon = tk.Label(
                ghost,
                text=account_button.cget("text"),
                bg=SURFACE_ELEVATED,
                fg=FG,
                font=("Arial", 10),
            )
        icon.pack(padx=8, pady=(8, 2))
        tk.Label(
            ghost,
            text=account_name.cget("text"),
            bg=SURFACE_ELEVATED,
            fg=FG,
            font=("Arial", 8),
        ).pack(padx=6, pady=(0, 7))
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
            row, col = divmod(index, COLS)
            widget = state["placeholder"] if name == source else self._account_items[name]
            widget.grid(row=row, column=col, padx=8, pady=8)

    def _layout_profile_order(self, order: list[str]):
        for index, name in enumerate(order):
            row, col = divmod(index, COLS)
            self._account_items[name].grid(row=row, column=col, padx=8, pady=8)

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

    def delete_profile(self, profile_name: str):
        display = self.launcher.get_display_name(profile_name)
        if self.ask_yes_no(
            "Confirmar Exclusão",
            f"Deseja realmente excluir a conta '{display}'?\nTodos os dados serão perdidos.",
        ):
            if self.launcher.delete_profile(self.current_platform, profile_name):
                self.load_profiles()

    def _account_dialog(self, mode: str, profile_name: str = None):
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
        header.pack(fill=tk.X, padx=24, pady=(22, 8))
        tk.Label(
            header,
            text="Editar conta" if is_edit else "Nova conta",
            bg=SURFACE,
            fg=FG,
            font=("Arial", 15, "bold"),
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
                anchor="w", padx=24, pady=(14, 6) if text.startswith("Nome") else (12, 6)
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
            e.pack(fill=tk.X, padx=24, ipady=8)
            return e

        current_display = (
            self.launcher.get_display_name(profile_name) if is_edit else ""
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
                self.launcher.set_profile_homepage(self.current_platform, target, site)
            else:
                if not name:
                    self.show_warning("Aviso", "Digite o nome da conta.")
                    return
                homepage = site or self.launcher.get_profile_homepage(self.current_platform, name)
                self.launcher.create_profile(self.current_platform, name, homepage=homepage)

            self.load_profiles()
            win.destroy()

        actions = tk.Frame(win, bg=SURFACE)
        actions.pack(fill=tk.X, padx=24, pady=20)
        self.btn(
            actions,
            "Salvar" if is_edit else "Criar",
            save,
            variant="primary",
            side=tk.LEFT,
            padx=(0, 8),
        )
        self.btn(actions, "Cancelar", win.destroy, variant="ghost", side=tk.LEFT)

    def run(self):
        self.root.mainloop()
