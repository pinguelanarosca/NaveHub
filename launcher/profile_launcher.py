"""
Módulo responsável por gerenciar perfis isolados por plataforma + Status A/B.
"""

import re
import subprocess
import shutil
import json
import time
import os
import socket
from pathlib import Path
from datetime import date
from launcher.eightu_popup_blocker import (
    EightUPopupBlockerSession,
    NinetyThreeHPopupBlockerSession,
    SevenSevenPopupBlockerSession,
    ThreeSixtyFiveGGPopupBlockerSession,
)

STATIC_PLATFORM = "Outras"
LAUNCH_DEBOUNCE_SECONDS = 0.75
DEFAULT_PLATFORM_HOMEAGES = {
    "8U": "https://8u111.com/index.html#/home",
    "777": "https://777vipv0.com/#/home",
    "365GG": "https://365gg2.com/#/home",
}
CHROME_RUNTIME_FILES = {
    "SingletonCookie",
    "SingletonLock",
    "SingletonSocket",
}
VISUAL_IDENTITY_KEYS = {
    "display_name",
    "label",
    "caption",
    "icon",
    "icon_path",
    "account_icon",
}


class ProfileLauncher:
    @staticmethod
    def get_default_homepage(platform: str) -> str | None:
        return DEFAULT_PLATFORM_HOMEAGES.get(platform)

    def __init__(self, config):
        self.config = config
        self.base_dir = Path.home() / ".navehub" / "platforms"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._initialization_marker = self.base_dir / ".navehub_initialized"
        self._last_launch_at = {}
        self._cdp_popup_blockers = {}

        # A instalação começa vazia. O marcador preserva esse estado e impede
        # que futuras versões recriem contas automaticamente na primeira abertura.
        if not self._initialization_marker.exists():
            try:
                self._initialization_marker.touch(exist_ok=True)
            except OSError as error:
                print(f"Aviso: não foi possível registrar a inicialização: {error}")

    def get_platform_dir(self, platform: str) -> Path:
        safe = platform.lower().replace(" ", "")
        path = self.base_dir / safe
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_profile_dir(self, platform: str, profile_name: str) -> Path:
        safe_name = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in profile_name.lower()
        )
        return self.get_platform_dir(platform) / safe_name

    def _profile_order_file(self, platform: str) -> Path:
        return self.get_platform_dir(platform) / "navehub_order.json"

    def _read_profile_order(self, platform: str) -> list[str]:
        """Ordem manual da grade; nomes ausentes são ignorados."""
        try:
            data = json.loads(self._profile_order_file(platform).read_text(encoding="utf-8"))
            order = data.get("profiles", []) if isinstance(data, dict) else data
            return [name for name in order if isinstance(name, str)]
        except (OSError, ValueError, TypeError):
            return []

    def save_profile_order(self, platform: str, profile_names: list[str]):
        """Persiste a ordem escolhida por arrastar e soltar na grade."""
        profiles = [
            directory.name
            for directory in self.get_platform_dir(platform).iterdir()
            if directory.is_dir()
        ]
        by_key = {name.lower(): name for name in profiles}
        saved = []
        seen = set()
        for name in profile_names:
            key = name.lower()
            actual = by_key.get(key)
            if actual and key not in seen:
                saved.append(actual)
                seen.add(key)
        for name in profiles:
            key = name.lower()
            if key not in seen:
                saved.append(name)
                seen.add(key)

        self._profile_order_file(platform).write_text(
            json.dumps({"profiles": saved}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _replace_in_profile_order(self, platform: str, old_name: str, new_name: str):
        order = self._read_profile_order(platform)
        if not order:
            return
        old_key = old_name.lower()
        self.save_profile_order(
            platform,
            [new_name if name.lower() == old_key else name for name in order],
        )

    def _remove_from_profile_order(self, platform: str, profile_name: str):
        order = self._read_profile_order(platform)
        if not order:
            return
        key = profile_name.lower()
        self.save_profile_order(
            platform,
            [name for name in order if name.lower() != key],
        )

    def _unique_profile_name(self, platform: str, base_name: str) -> str:
        existing = {name.lower() for name in self.list_profiles(platform)}
        candidate = f"{base_name}_copia"
        if candidate.lower() not in existing:
            return candidate

        index = 2
        while True:
            candidate = f"{base_name}_copia_{index}"
            if candidate.lower() not in existing:
                return candidate
            index += 1

    def get_display_name(self, profile_name: str) -> str:
        """
        Nome visível ao usuário.
        Esconde só a referência interna de ordem (1, 2, 3… no início).
        Mantém o nome real da conta.

        Exemplos:
          13444vip8  -> 3444VIP8   (interno 1)
          24202vip7  -> 4202VIP7   (interno 2)
          101918vip3 -> 1918VIP3   (interno 10)
          4kaosvip2  -> kaosVIP2   (interno 4)
          tirovip1   -> tiroVIP1   (sem prefixo de ordem)
        """
        compact = profile_name.replace("_", "").replace(" ", "").strip()
        if not compact:
            return profile_name

        # Prefixo de ordem 1–35 + código 4 dígitos + VIP + nível
        m = re.match(r"^(\d{1,2})(\d{4}vip\d+)$", compact, re.IGNORECASE)
        if m and 1 <= int(m.group(1)) <= 35:
            rest = m.group(2)
        else:
            # Prefixo de ordem + nome começando com letra (ex.: 4kaosVIP2)
            m = re.match(r"^(\d{1,2})([A-Za-z].+)$", compact)
            if m and 1 <= int(m.group(1)) <= 35:
                rest = m.group(2)
            else:
                rest = compact

        rest = re.sub(r"vip(\d+)$", lambda x: f"VIP{x.group(1)}", rest, flags=re.IGNORECASE)
        return rest

    def create_profile(self, platform: str, profile_name: str, homepage: str = None) -> Path:
        profile_dir = self.get_profile_dir(platform, profile_name)
        profile_dir.mkdir(parents=True, exist_ok=True)

        if homepage is None:
            homepage = self.get_default_homepage(platform)
        if homepage:
            self.set_profile_homepage(platform, profile_name, homepage)

        return profile_dir

    def _read_profile_data(self, platform: str, profile_name: str) -> dict:
        profile_dir = self.get_profile_dir(platform, profile_name)
        settings_file = profile_dir / "navehub.json"

        if settings_file.exists():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _write_profile_data(self, platform: str, profile_name: str, data: dict):
        profile_dir = self.get_profile_dir(platform, profile_name)
        profile_dir.mkdir(parents=True, exist_ok=True)
        settings_file = profile_dir / "navehub.json"
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profile_homepage(self, platform: str, profile_name: str) -> str:
        data = self._read_profile_data(platform, profile_name)
        return data.get("homepage", self.config.get("homepage", "https://site.com"))

    def set_profile_homepage(self, platform: str, profile_name: str, homepage: str):
        data = self._read_profile_data(platform, profile_name)
        data["homepage"] = homepage
        self._write_profile_data(platform, profile_name, data)

    def mark_as_accessed(self, platform: str, profile_name: str):
        """Registra o acesso apenas nas plataformas com status diário."""
        if platform == STATIC_PLATFORM:
            return

        data = self._read_profile_data(platform, profile_name)
        data["last_access"] = date.today().isoformat()
        self._write_profile_data(platform, profile_name, data)

    def get_profile_status(self, platform: str, profile_name: str) -> str:
        # Os perfis de "Outras" não têm status vinculado ao dia ou ao acesso.
        if platform == STATIC_PLATFORM:
            return "A"

        data = self._read_profile_data(platform, profile_name)
        last_access = data.get("last_access")

        if last_access == date.today().isoformat():
            return "A"
        return "B"

    def reset_profile_statuses(self, platform: str) -> int:
        """Restaura todas as contas da plataforma ao estado B.

        O reset remove apenas o registro de acesso do dia. Cookies, login,
        site configurado e ordem manual das contas não são alterados.
        """
        if platform == STATIC_PLATFORM:
            return 0

        changed = 0
        for profile_name in self.list_profiles(platform):
            data = self._read_profile_data(platform, profile_name)
            if "last_access" not in data:
                continue
            data.pop("last_access", None)
            self._write_profile_data(platform, profile_name, data)
            changed += 1
        return changed

    def get_window_size(self) -> tuple[int, int]:
        """Retorna um tamanho inicial adequado à tela disponível."""
        def positive_int(value, default):
            try:
                size = int(value)
            except (TypeError, ValueError):
                return default
            return size if size > 0 else default

        width = 500
        height = 900

        return (
            width,
            height,
        )

    def set_window_position(self, x: int, y: int):
        """Define a posição da próxima janela de conta nesta execução."""
        self.window_position = (max(0, int(x)), max(0, int(y)))

    def get_window_position(self) -> tuple[int, int] | None:
        """Retorna a posição calculada pela janela principal, se houver."""
        return getattr(self, "window_position", None)

    def get_browser_app_id(self, platform: str) -> str:
        """Identificador da janela do Chrome usado pelo gerenciador gráfico."""
        safe_platform = re.sub(r"[^a-z0-9]+", "-", platform.lower()).strip("-")
        return f"navehub-{safe_platform or 'conta'}"

    def get_browser_icon_path(self, platform: str) -> Path:
        """Ícone exibido pelo sistema para a janela de uma conta.

        Para as plataformas com status diário, a janela usa o ícone B. A área
        "Outras" não possui estado B, então preserva seu ícone próprio.
        """
        project_dir = Path(__file__).resolve().parent.parent
        if platform == STATIC_PLATFORM:
            return project_dir / "icons" / "accounts" / "outras.png"

        safe_platform = platform.lower().replace(" ", "")
        return project_dir / "icons" / "accounts" / f"{safe_platform}_b.webp"

    def ensure_browser_desktop_entry(self, platform: str, browser: str) -> str:
        """Registra o ícone da janela Chrome no menu/dock do Linux.

        O Chrome recebe a mesma classe via ``--class``. Assim, o gerenciador
        de janelas encontra esta entrada .desktop e não usa o ícone genérico
        de engrenagem. Essa associação não faz parte do perfil do navegador.
        """
        app_id = self.get_browser_app_id(platform)
        icon_path = self.get_browser_icon_path(platform)
        desktop_dir = Path.home() / ".local" / "share" / "applications"
        desktop_file = desktop_dir / f"{app_id}.desktop"
        platform_name = platform.replace("\n", " ").replace("\r", " ")
        contents = (
            "[Desktop Entry]\n"
            "Version=1.0\n"
            "Type=Application\n"
            f"Name=NaveHub — {platform_name}\n"
            f"Exec={browser} --class={app_id}\n"
            f"Icon={icon_path}\n"
            f"StartupWMClass={app_id}\n"
            "Terminal=false\n"
            "NoDisplay=true\n"
        )

        try:
            desktop_dir.mkdir(parents=True, exist_ok=True)
            if not desktop_file.exists() or desktop_file.read_text(encoding="utf-8") != contents:
                desktop_file.write_text(contents, encoding="utf-8")
        except OSError as e:
            # O perfil continua abrindo mesmo se o ambiente gráfico não
            # permitir registrar o atalho; apenas o ícone padrão é usado.
            print(f"Aviso: não foi possível registrar o ícone da janela: {e}")

        return app_id

    def get_platform_status(self, platform: str) -> str:
        if platform == STATIC_PLATFORM:
            return "A"

        profiles = self.list_profiles(platform)
        if not profiles:
            return "B"

        for profile_name in profiles:
            if self.get_profile_status(platform, profile_name) == "B":
                return "B"
        return "A"


    def _reserve_local_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def _cleanup_cdp_popup_blockers(self):
        for profile_dir, session in list(self._cdp_popup_blockers.items()):
            if not session.is_alive() or not self._profile_is_running(profile_dir):
                session.stop()
                self._cdp_popup_blockers.pop(profile_dir, None)

    def launch_profile(self, platform: str, profile_name: str):
        launch_key = (platform, profile_name)
        now = time.monotonic()
        last_launch = self._last_launch_at.get(launch_key)
        if last_launch is not None and now - last_launch < LAUNCH_DEBOUNCE_SECONDS:
            # Ignora o segundo evento de clique do mesmo cartão.
            return True

        profile_dir = self.create_profile(platform, profile_name)
        browser = self.config.get("browser", "google-chrome")
        homepage = self.get_profile_homepage(platform, profile_name)
        window_width, window_height = self.get_window_size()
        window_position = self.get_window_position()
        app_id = self.ensure_browser_desktop_entry(platform, browser)
        popup_blocker_class = {
            "8U": EightUPopupBlockerSession,
            "777": SevenSevenPopupBlockerSession,
            "365GG": ThreeSixtyFiveGGPopupBlockerSession,
            "93H": NinetyThreeHPopupBlockerSession,
        }.get(platform)
        cdp_port = self._reserve_local_port() if popup_blocker_class is not None else None
        cmd = [
            browser,
            f"--user-data-dir={profile_dir}",
            *(
                [f"--remote-debugging-port={cdp_port}", "--remote-debugging-address=127.0.0.1"]
                if cdp_port is not None
                else []
            ),
            "--no-first-run",
            "--no-default-browser-check",
            # No Wayland o Chrome anuncia o app_id "google-chrome" e ignora
            # a classe personalizada para o dock. X11 respeita WM_CLASS,
            # permitindo que a entrada .desktop use o ícone B da conta.
            "--ozone-platform=x11",
            # Associa a janela à entrada .desktop que contém o ícone B.
            f"--class={app_id}",
            # Usa o padrão salvo em config.json, em vez de reutilizar uma
            # geometria grande que o Chrome possa ter memorizado no perfil.
            f"--window-size={window_width},{window_height}",
            *(
                [f"--window-position={window_position[0]},{window_position[1]}"]
                if window_position is not None
                else []
            ),
            # Abre como app (PWA): sem abas ou barra de endereço, mantendo
            # o mesmo perfil isolado da conta.
            f"--app={homepage}",
        ]

        try:
            process = subprocess.Popen(cmd)
        except FileNotFoundError:
            return False

        if popup_blocker_class is not None and cdp_port is not None:
            self._cleanup_cdp_popup_blockers()
            session = popup_blocker_class(process, profile_dir, cdp_port)
            self._cdp_popup_blockers[profile_dir] = session
            session.start()

        self._last_launch_at[launch_key] = now
        self.mark_as_accessed(platform, profile_name)
        return True

    @staticmethod
    def _profile_is_running(profile_dir: Path) -> bool:
        """Verifica se ainda existe Chrome usando este perfil."""
        lock = profile_dir / "SingletonLock"
        if not lock.exists() and not lock.is_symlink():
            return False
        try:
            target = os.readlink(lock) if lock.is_symlink() else ""
        except OSError:
            return True
        if "-" in target:
            pid_text = target.rsplit("-", 1)[-1]
            if pid_text.isdigit():
                try:
                    os.kill(int(pid_text), 0)
                    return True
                except OSError:
                    return False
        return True

    def rename_profile(self, platform: str, old_name: str, new_name: str) -> bool:
        old_dir = self.get_profile_dir(platform, old_name)
        new_dir = self.get_profile_dir(platform, new_name)

        if old_dir.exists() and not new_dir.exists():
            old_dir.rename(new_dir)
            self._replace_in_profile_order(platform, old_name, new_name)
            return True
        return False

    def delete_profile(self, platform: str, profile_name: str) -> bool:
        profile_dir = self.get_profile_dir(platform, profile_name)
        if profile_dir.exists():
            shutil.rmtree(profile_dir)
            self._remove_from_profile_order(platform, profile_name)
            return True
        return False

    def clone_profile(self, platform: str, profile_name: str) -> str | None:
        source_dir = self.get_profile_dir(platform, profile_name)
        if not source_dir.exists():
            return None

        clone_name = self._unique_profile_name(platform, profile_name)
        clone_dir = self.get_profile_dir(platform, clone_name)
        try:
            shutil.copytree(
                source_dir,
                clone_dir,
                ignore=shutil.ignore_patterns(*CHROME_RUNTIME_FILES),
                symlinks=True,
            )
        except OSError:
            if clone_dir.exists():
                shutil.rmtree(clone_dir, ignore_errors=True)
            return None

        order = self._read_profile_order(platform)
        if order:
            inserted = []
            source_key = profile_name.lower()
            added = False
            for name in order:
                inserted.append(name)
                if name.lower() == source_key:
                    inserted.append(clone_name)
                    added = True
            if not added:
                inserted.append(clone_name)
            self.save_profile_order(platform, inserted)

        return clone_name

    def heavy_clean_profile(self, platform: str, profile_name: str) -> bool:
        profile_dir = self.get_profile_dir(platform, profile_name)
        if not profile_dir.exists():
            return False

        settings = self._read_profile_data(platform, profile_name)
        visual_settings = {
            key: value
            for key, value in settings.items()
            if key in VISUAL_IDENTITY_KEYS
        }
        try:
            shutil.rmtree(profile_dir)
            profile_dir.mkdir(parents=True, exist_ok=True)
            self._write_profile_data(platform, profile_name, visual_settings)
        except OSError:
            return False
        return True

    def list_profiles(self, platform: str) -> list:
        platform_dir = self.get_platform_dir(platform)
        if not platform_dir.exists():
            return []

        profiles = [d.name for d in platform_dir.iterdir() if d.is_dir()]
        if platform != "8U":
            default_order = sorted(profiles)
        else:
            def eight_u_sort_key(profile_name: str):
                vip_match = re.search(r"vip(\d+)$", profile_name, re.IGNORECASE)
                vip_level = int(vip_match.group(1)) if vip_match else -1
                return (
                    -vip_level,
                    profile_name.lower(),
                )

            default_order = sorted(profiles, key=eight_u_sort_key)

        by_key = {name.lower(): name for name in profiles}
        saved_order = self._read_profile_order(platform)
        ordered = []
        seen = set()
        for name in saved_order:
            key = name.lower()
            actual = by_key.get(key)
            if actual and key not in seen:
                ordered.append(actual)
                seen.add(key)
        ordered.extend(name for name in default_order if name.lower() not in seen)
        return ordered
