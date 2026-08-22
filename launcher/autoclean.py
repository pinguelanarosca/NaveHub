"""
AutoClean conservador para perfis Chromium usados pelo NaveHub.

A regra central é simples: somente arquivos e diretórios com função
descartável conhecida entram na lista de remoção. Todo o restante é preservado.
"""

from __future__ import annotations

import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, NamedTuple


class DisposableRule(NamedTuple):
    kind: str
    purpose: str


ROOT_DISPOSABLE = {
    "BrowserMetrics": DisposableRule("dir", "métricas locais de uso/execução do Chrome"),
    "Crashpad": DisposableRule("dir", "relatórios temporários de falha do Chrome"),
    "Crash Reports": DisposableRule("dir", "relatórios temporários de falha do Chrome"),
    "ShaderCache": DisposableRule("dir", "cache recompilável de shaders gráficos"),
    "GrShaderCache": DisposableRule("dir", "cache recompilável de shaders gráficos"),
    "GPUCache": DisposableRule("dir", "cache recompilável da GPU"),
    "DawnCache": DisposableRule("dir", "cache recompilável do backend gráfico Dawn/WebGPU"),
    "GraphiteDawnCache": DisposableRule("dir", "cache recompilável do backend gráfico Graphite/Dawn"),
    "component_crx_cache": DisposableRule("dir", "cache de componentes baixados pelo Chromium"),
    "SingletonCookie": DisposableRule("file", "marcador de execução da instância Chromium"),
    "SingletonLock": DisposableRule("any", "lock de execução da instância Chromium"),
    "SingletonSocket": DisposableRule("any", "socket local da instância Chromium"),
}

PROFILE_DISPOSABLE = {
    "Cache": DisposableRule("dir", "cache HTTP recompilável do perfil"),
    "Code Cache": DisposableRule("dir", "cache recompilável de JavaScript/WebAssembly"),
    "GPUCache": DisposableRule("dir", "cache recompilável da GPU"),
    "DawnCache": DisposableRule("dir", "cache recompilável do backend gráfico Dawn/WebGPU"),
    "GraphiteDawnCache": DisposableRule("dir", "cache recompilável do backend gráfico Graphite/Dawn"),
    "GrShaderCache": DisposableRule("dir", "cache recompilável de shaders gráficos"),
    "ShaderCache": DisposableRule("dir", "cache recompilável de shaders gráficos"),
    "Media Cache": DisposableRule("dir", "cache recompilável de mídia"),
}

PROTECTED_ROOT = {
    "Local State": "estado global do Chromium e metadados de criptografia do perfil",
    "First Run": "marcador interno de inicialização do Chromium",
    "Last Version": "versão usada pelo Chromium para migrações do perfil",
}

PROTECTED_PROFILE = {
    "Preferences": "preferências do perfil, permissões e estado do navegador/app",
    "Secure Preferences": "preferências protegidas do perfil",
    "Login Data": "banco de senhas salvas usado no autopreenchimento",
    "Login Data For Account": "banco auxiliar de senhas salvas usado no autopreenchimento",
    "Web Data": "banco de autofill, dados de formulários e cartões",
    "Cookies": "cookies de sessão quando o Chromium usa layout antigo",
    "Network": "cookies e estado de rede usados para sessão persistente",
    "Local Storage": "armazenamento local de sites usado por sessões e apps",
    "Session Storage": "armazenamento de sessão de sites",
    "IndexedDB": "bancos locais de sites usados por sessões e apps",
    "File System": "armazenamento local persistente de sites",
    "databases": "bancos locais legados de sites",
    "Extension State": "estado local de extensões e componentes do perfil",
    "Sessions": "restauração de sessão/janelas do Chromium",
    "Sync Data": "estado de sincronização do perfil",
    "Shared Dictionary": "dados de rede que podem ser reaproveitados por sites",
}


class ChromiumProfileAutoClean:
    def __init__(
        self,
        log_file: Path,
        is_profile_running: Callable[[Path], bool] | None = None,
    ):
        self.log_file = log_file
        self.is_profile_running = is_profile_running
        self._log_lock = threading.Lock()

    def clean(self, profile_dir: Path, *, platform: str, profile_name: str) -> bool:
        profile_dir = Path(profile_dir)
        self._log_header(platform, profile_name, profile_dir)

        if not profile_dir.exists():
            self._log("IGNORADO", profile_dir, "perfil não existe")
            return False

        if self.is_profile_running is not None and self.is_profile_running(profile_dir):
            self._log("IGNORADO", profile_dir, "perfil ainda está em execução")
            return False

        removed = 0
        preserved = 0

        for path, rule in self._iter_disposable_candidates(profile_dir):
            if not path.exists() and not path.is_symlink():
                continue
            if not self._matches_kind(path, rule.kind):
                self._log("PRESERVADO", path, f"tipo inesperado para {rule.purpose}")
                preserved += 1
                continue
            try:
                self._remove_path(path)
            except OSError as error:
                self._log("PRESERVADO", path, f"falha ao remover {rule.purpose}: {error}")
                preserved += 1
            else:
                self._log("REMOVIDO", path, rule.purpose)
                removed += 1

        for path, purpose in self._iter_protected_paths(profile_dir):
            if path.exists() or path.is_symlink():
                self._log("PRESERVADO", path, purpose)
                preserved += 1

        for path in self._iter_unclassified_direct_paths(profile_dir):
            self._log("PRESERVADO", path, "função não classificada como descartável com segurança")
            preserved += 1

        self._log("CONCLUÍDO", profile_dir, f"{removed} removidos, {preserved} preservados")
        return True

    def _iter_disposable_candidates(self, profile_dir: Path):
        for name, rule in ROOT_DISPOSABLE.items():
            yield profile_dir / name, rule

        for chrome_profile_dir in self._iter_chrome_profile_dirs(profile_dir):
            for name, rule in PROFILE_DISPOSABLE.items():
                yield chrome_profile_dir / name, rule

    def _iter_protected_paths(self, profile_dir: Path):
        for name, purpose in PROTECTED_ROOT.items():
            yield profile_dir / name, purpose

        for chrome_profile_dir in self._iter_chrome_profile_dirs(profile_dir):
            yield chrome_profile_dir, "contêiner de dados do perfil Chromium da conta"
            for name, purpose in PROTECTED_PROFILE.items():
                yield chrome_profile_dir / name, purpose

    def _iter_unclassified_direct_paths(self, profile_dir: Path):
        classified_root = set(ROOT_DISPOSABLE) | set(PROTECTED_ROOT)
        classified_profile = set(PROFILE_DISPOSABLE) | set(PROTECTED_PROFILE)
        chrome_profile_dirs = set(self._iter_chrome_profile_dirs(profile_dir))

        try:
            root_children = list(profile_dir.iterdir())
        except OSError:
            return

        for child in root_children:
            if child not in chrome_profile_dirs and child.name not in classified_root:
                yield child

        for chrome_profile_dir in chrome_profile_dirs:
            try:
                children = list(chrome_profile_dir.iterdir())
            except OSError:
                continue
            for child in children:
                if child.name not in classified_profile:
                    yield child

    def _iter_chrome_profile_dirs(self, user_data_dir: Path):
        try:
            children = list(user_data_dir.iterdir())
        except OSError:
            return

        for child in children:
            if not child.is_dir():
                continue
            if child.name in {"Default", "Guest Profile", "System Profile"}:
                yield child
                continue
            if child.name.startswith("Profile ") and any(
                (child / marker).exists()
                for marker in ("Preferences", "Login Data", "Web Data", "Network")
            ):
                yield child

    @staticmethod
    def _matches_kind(path: Path, kind: str) -> bool:
        if kind == "any":
            return True
        if kind == "dir":
            return path.is_dir() and not path.is_symlink()
        if kind == "file":
            return path.is_file() or path.is_symlink()
        return False

    @staticmethod
    def _remove_path(path: Path):
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)

    def _log_header(self, platform: str, profile_name: str, profile_dir: Path):
        self._log(
            "INÍCIO",
            profile_dir,
            f"AutoClean plataforma={platform!r} conta={profile_name!r}",
        )

    def _log(self, action: str, path: Path, detail: str):
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        line = f"{timestamp} [{action}] {path} — {detail}\n"
        with self._log_lock:
            try:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
                with self.log_file.open("a", encoding="utf-8") as log:
                    log.write(line)
            except OSError:
                pass
        print(line.rstrip())
