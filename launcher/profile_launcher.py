"""
Módulo responsável por gerenciar perfis isolados por plataforma + Status A/B.
"""

import http.client
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from launcher.autoclean import ChromiumProfileAutoClean
from launcher.eightu_popup_blocker import (
    EightUPopupBlockerSession,
    NaveHubTitleSession,
    NinetyThreeHPopupBlockerSession,
    SevenSevenPopupBlockerSession,
    ThreeSixtyFiveGGPopupBlockerSession,
    build_page_title_source,
)

STATIC_PLATFORM = "Legalizadas"
LEGACY_STATIC_PLATFORMS = ("Outras", "Outros", "Plataformas Autorizadas")
LAUNCH_DEBOUNCE_SECONDS = 0.75
FAVICON_WORKERS = 3
FAVICON_REQUEST_TIMEOUT = 5
FAVICON_RETRIES = 2
FAVICON_MAX_BYTES = 512 * 1024
DEFAULT_PLATFORM_HOMEAGES = {
    "8U": "https://8u111.com/index.html#/home",
    "777": "https://777vipv0.com/#/home",
    "365GG": "https://365gg2.com/#/home",
}

V14_SEED_MARKER = ".navehub_seed_v1_4"
V14_STATIC_PLATFORM_ACCOUNTS = [
    ("Betsul", "https://betsul.bet.br/"),
    ("LanceDeSorte", "https://lancedesorte.bet.br/"),
    ("Novibet", "https://novibet.bet.br/"),
    ("7Games", "https://7games.bet.br/"),
    ("Pixbet", "https://pix.bet.br/"),
    ("Betdasorte", "https://betdasorte.bet.br/"),
    ("Bandbet", "https://bandbet.bet.br/"),
    ("HiperBet", "https://hiper.bet.br/"),
    ("Jogao", "https://jogao.bet.br/"),
    ("Sportingbet", "https://sportingbet.bet.br/"),
    ("Rivalo", "https://rivalo.bet.br/"),
    ("Lottoland", "https://lottoland.bet.br/"),
    ("Energia", "https://energia.bet.br/"),
    ("1Win", "https://1win.com/"),
    ("Parimatch", "https://parimatch.com/"),
    ("Vai de Bet", "https://vaidebet.bet.br/"),
    ("Bet Gorillas", "https://betgorillas.bet.br/"),
    ("BravoBet", "https://bravo.bet.br/"),
    ("VEMDEBET", "https://vemdebet.bet/"),
    ("Joga Junto", "https://jogajunto.bet.br/"),
    ("AcertaBet", "https://acertabet.bet/"),
    ("7K", "https://7k.bet.br/"),
    ("Cassino.bet.br", "https://cassino.bet.br/"),
    ("Vera", "https://vera.bet.br/"),
    ("Betano", "https://betano.bet.br/"),
    ("Bullsbet", "https://bullsbet.bet.br/"),
    ("Zeroum", "https://zeroum.bet/"),
    ("Superbet", "https://superbet.bet.br/"),
    ("Betpix", "https://betpix365.bet.br/"),
    ("BetVip", "https://betvip.bet.br/"),
    ("Apostatudo", "https://apostatudo.bet.br/"),
    ("Apostou", "https://apostou.bet.br/"),
    ("F12", "https://f12.bet.br/"),
    ("Pitaco", "https://pitaco.bet.br/"),
    ("EstrelaBet", "https://estrelabet.bet.br/"),
    ("Betnacional", "https://betnacional.bet.br/"),
    ("Betão", "https://betao.bet.br/"),
    ("Pagol", "https://pagol.bet.br/"),
    ("R7 Bet", "https://r7.bet.br/"),
    ("Ultra Bet", "https://ultra.bet.br/"),
    ("BRX Bet", "https://brx.bet.br/"),
    ("MC Games", "https://mcgames.bet.br/"),
    ("ICE", "https://ice.bet.br/"),
    ("BetBoom", "https://betboom.bet.br/"),
    ("Sorte na Bet", "https://sortenabet.bet.br/"),
]

CHROME_RUNTIME_FILES = {
    "SingletonCookie",
    "SingletonLock",
    "SingletonSocket",
}


class FaviconLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "link":
            return
        values = {name.lower(): value for name, value in attrs if value}
        rel = values.get("rel", "").lower()
        href = values.get("href")
        if href and "icon" in rel:
            self.hrefs.append(href)


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
        self._favicon_queue = queue.Queue()
        self._favicon_lock = threading.Lock()
        self._favicon_pending = set()
        self._favicon_batches = {}
        self._favicon_global_running = False

        self._start_favicon_workers()

        self.autoclean = ChromiumProfileAutoClean(
            self.base_dir.parent / "autoclean.log",
            self._profile_is_running,
        )

        # Uma instalação começa vazia. O marcador preserva esse estado e
        # impede que futuras versões recriem contas automaticamente na
        # primeira abertura.
        if not self._initialization_marker.exists():
            try:
                self._initialization_marker.touch(exist_ok=True)
            except OSError as error:
                print(
                    f"Aviso: não foi possível registrar a inicialização: {error}"
                )

        self.ensure_v14_accounts()

    def _start_favicon_workers(self):
        for index in range(FAVICON_WORKERS):
            thread = threading.Thread(
                target=self._favicon_worker,
                name=f"navehub-favicon-{index + 1}",
                daemon=True,
            )
            thread.start()

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
        """Lê a ordem manual da grade; nomes ausentes são ignorados."""
        try:
            data = json.loads(
                self._profile_order_file(platform).read_text(
                    encoding="utf-8"
                )
            )
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

        # Garante que perfis existentes mas ausentes no arquivo de ordem
        # não sejam perdidos.
        for name in profiles:
            key = name.lower()

            if key not in seen:
                saved.append(name)
                seen.add(key)

        self._profile_order_file(platform).write_text(
            json.dumps(
                {"profiles": saved},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _replace_in_profile_order(
        self,
        platform: str,
        old_name: str,
        new_name: str,
    ):
        order = self._read_profile_order(platform)

        if not order:
            return

        old_key = old_name.lower()

        self.save_profile_order(
            platform,
            [
                new_name if name.lower() == old_key else name
                for name in order
            ],
        )

    def _remove_from_profile_order(
        self,
        platform: str,
        profile_name: str,
    ):
        order = self._read_profile_order(platform)

        if not order:
            return

        key = profile_name.lower()

        self.save_profile_order(
            platform,
            [
                name
                for name in order
                if name.lower() != key
            ],
        )

    def _unique_profile_name(
        self,
        platform: str,
        base_name: str,
    ) -> str:
        existing = {
            name.lower()
            for name in self.list_profiles(platform)
        }

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
        m = re.match(
            r"^(\d{1,2})(\d{4}vip\d+)$",
            compact,
            re.IGNORECASE,
        )

        if m and 1 <= int(m.group(1)) <= 35:
            rest = m.group(2)
        else:
            # Prefixo de ordem + nome começando com letra
            # (ex.: 4kaosVIP2)
            m = re.match(
                r"^(\d{1,2})([A-Za-z].+)$",
                compact,
            )

            if m and 1 <= int(m.group(1)) <= 35:
                rest = m.group(2)
            else:
                rest = compact

        rest = re.sub(
            r"vip(\d+)$",
            lambda x: f"VIP{x.group(1)}",
            rest,
            flags=re.IGNORECASE,
        )

        return rest

    def get_profile_display_name(
        self,
        platform: str,
        profile_name: str,
    ) -> str:
        data = self._read_profile_data(
            platform,
            profile_name,
        )

        display_name = data.get("display_name")

        if isinstance(display_name, str) and display_name.strip():
            return display_name

        return self.get_display_name(profile_name)

    def get_profile_icon_path(
        self,
        platform: str,
        profile_name: str,
    ) -> Path | None:
        if platform != STATIC_PLATFORM:
            return None

        data = self._read_profile_data(
            platform,
            profile_name,
        )

        icon_path = data.get("icon_path") or data.get("account_icon")

        if not isinstance(icon_path, str) or not icon_path.strip():
            return None

        path = Path(icon_path).expanduser()

        if not path.is_absolute():
            path = self.get_profile_dir(
                platform,
                profile_name,
            ) / path

        if path.exists() and path.is_file():
            return path

        return None

    def create_profile(
        self,
        platform: str,
        profile_name: str,
        homepage: str | None = None,
    ) -> Path:
        profile_dir = self.get_profile_dir(
            platform,
            profile_name,
        )

        created = not profile_dir.exists()

        profile_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        if homepage is None:
            homepage = self.get_default_homepage(platform)

        if homepage:
            self.set_profile_homepage(
                platform,
                profile_name,
                homepage,
            )

            if created and platform == STATIC_PLATFORM:
                self.enqueue_static_profile_favicon(profile_name)

        return profile_dir

    def _read_profile_data(
        self,
        platform: str,
        profile_name: str,
    ) -> dict:
        profile_dir = self.get_profile_dir(
            platform,
            profile_name,
        )

        settings_file = profile_dir / "navehub.json"

        if settings_file.exists():
            try:
                with open(
                    settings_file,
                    encoding="utf-8",
                ) as f:
                    return json.load(f)
            except Exception:
                pass

        return {}

    def _write_profile_data(
        self,
        platform: str,
        profile_name: str,
        data: dict,
    ):
        profile_dir = self.get_profile_dir(
            platform,
            profile_name,
        )

        profile_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        settings_file = profile_dir / "navehub.json"
        tmp_file = settings_file.with_suffix(".json.tmp")

        with open(
            tmp_file,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False,
            )

        os.replace(
            tmp_file,
            settings_file,
        )

    def get_profile_homepage(
        self,
        platform: str,
        profile_name: str,
    ) -> str:
        data = self._read_profile_data(
            platform,
            profile_name,
        )

        return data.get(
            "homepage",
            self.config.get(
                "homepage",
                "https://site.com",
            ),
        )

    def set_profile_homepage(
        self,
        platform: str,
        profile_name: str,
        homepage: str,
    ):
        data = self._read_profile_data(
            platform,
            profile_name,
        )

        data["homepage"] = homepage

        self._write_profile_data(
            platform,
            profile_name,
            data,
        )

    def set_profile_display_name(
        self,
        platform: str,
        profile_name: str,
        display_name: str,
    ):
        data = self._read_profile_data(
            platform,
            profile_name,
        )

        data["display_name"] = display_name

        self._write_profile_data(
            platform,
            profile_name,
            data,
        )

    def enqueue_static_platform_favicons(
        self,
        *,
        force=False,
        on_progress=None,
        on_complete=None,
    ) -> bool:
        with self._favicon_lock:
            if self._favicon_global_running:
                return False

            profiles = self.list_profiles(STATIC_PLATFORM)

            batch_id = object()

            self._favicon_global_running = True

            self._favicon_batches[batch_id] = {
                "remaining": 0,
                "result": {
                    "updated": 0,
                    "skipped": 0,
                    "failed": 0,
                },
                "on_progress": on_progress,
                "on_complete": on_complete,
                "global": True,
            }

            queued = 0

            for profile_name in profiles:
                if self._enqueue_static_profile_favicon_locked(
                    profile_name,
                    force,
                    batch_id,
                ):
                    queued += 1

            self._favicon_batches[batch_id]["remaining"] = queued

        if queued == 0:
            self._finish_favicon_batch(batch_id)

        return True

    def enqueue_static_profile_favicon(
        self,
        profile_name: str,
        *,
        force=False,
        on_complete=None,
    ) -> bool:
        with self._favicon_lock:
            batch_id = object()

            self._favicon_batches[batch_id] = {
                "remaining": 0,
                "result": {
                    "updated": 0,
                    "skipped": 0,
                    "failed": 0,
                },
                "on_progress": None,
                "on_complete": on_complete,
                "global": False,
            }

            queued = self._enqueue_static_profile_favicon_locked(
                profile_name,
                force,
                batch_id,
            )

            self._favicon_batches[batch_id]["remaining"] = (
                1 if queued else 0
            )

        if not queued:
            self._finish_favicon_batch(batch_id)

        return queued

    def _enqueue_static_profile_favicon_locked(
        self,
        profile_name: str,
        force: bool,
        batch_id,
    ) -> bool:
        key = (
            STATIC_PLATFORM,
            profile_name.lower(),
        )

        if key in self._favicon_pending:
            return False

        self._favicon_pending.add(key)

        self._favicon_queue.put(
            (
                profile_name,
                force,
                batch_id,
                key,
            )
        )

        return True

    def _favicon_worker(self):
        while True:
            profile_name, force, batch_id, key = (
                self._favicon_queue.get()
            )

            try:
                status = self.sync_static_profile_favicon(
                    profile_name,
                    force=force,
                )
            except Exception as error:
                print(
                    "Aviso: falha inesperada ao atualizar "
                    f"favicon de {profile_name}: {error}"
                )
                status = "failed"
            finally:
                with self._favicon_lock:
                    self._favicon_pending.discard(key)

                self._favicon_queue.task_done()

            self._record_favicon_result(
                batch_id,
                profile_name,
                status,
            )

    def _record_favicon_result(
        self,
        batch_id,
        profile_name: str,
        status: str,
    ):
        callbacks: list[
            tuple[
                Callable[..., None],
                object,
                object,
                object,
            ]
        ] = []

        with self._favicon_lock:
            batch = self._favicon_batches.get(batch_id)

            if batch is None:
                return

            batch["result"][status] = (
                batch["result"].get(status, 0) + 1
            )

            batch["remaining"] -= 1

            if batch["on_progress"]:
                callbacks.append(
                    (
                        batch["on_progress"],
                        profile_name,
                        status,
                        dict(batch["result"]),
                    )
                )

            if batch["remaining"] <= 0:
                callbacks.append(
                    (
                        self._finish_favicon_batch,
                        batch_id,
                        None,
                        None,
                    )
                )

        for callback, name, item_status, result in callbacks:
            if item_status is None and result is None:
                callback(name)
            else:
                callback(
                    name,
                    item_status,
                    result,
                )

    def _finish_favicon_batch(self, batch_id):
        callback = None
        result = None

        with self._favicon_lock:
            batch = self._favicon_batches.pop(
                batch_id,
                None,
            )

            if batch is None:
                return

            if batch.get("global"):
                self._favicon_global_running = False

            callback = batch.get("on_complete")
            result = dict(batch["result"])

        if callback:
            callback(result)

    def sync_static_profile_favicon(
        self,
        profile_name: str,
        *,
        force=False,
    ) -> str:
        data = self._read_profile_data(
            STATIC_PLATFORM,
            profile_name,
        )

        homepage = data.get("homepage")

        normalized_homepage = (
            self._normalize_favicon_homepage(homepage)
        )

        if normalized_homepage is None:
            return "skipped"

        if (
            not force
            and self._profile_has_valid_favicon(
                STATIC_PLATFORM,
                profile_name,
                data,
            )
        ):
            return "skipped"

        favicon = self._download_favicon(
            normalized_homepage
        )

        if favicon is None:
            return "failed"

        content, extension = favicon

        profile_dir = self.get_profile_dir(
            STATIC_PLATFORM,
            profile_name,
        )

        icon_file = (
            profile_dir
            / f"navehub_favicon{extension}"
        )

        tmp_file = (
            profile_dir
            / f".navehub_favicon{extension}.tmp"
        )

        try:
            tmp_file.write_bytes(content)
            os.replace(
                tmp_file,
                icon_file,
            )
        except OSError:
            try:
                tmp_file.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            return "failed"

        data["icon_path"] = str(icon_file)

        self._write_profile_data(
            STATIC_PLATFORM,
            profile_name,
            data,
        )

        return "updated"

    def _profile_has_valid_favicon(
        self,
        platform: str,
        profile_name: str,
        data: dict | None = None,
    ) -> bool:
        if data is None:
            data = self._read_profile_data(
                platform,
                profile_name,
            )

        icon_path = (
            data.get("icon_path")
            or data.get("account_icon")
        )

        if (
            not isinstance(icon_path, str)
            or not icon_path.strip()
        ):
            return False

        path = Path(icon_path).expanduser()

        if not path.is_absolute():
            path = (
                self.get_profile_dir(
                    platform,
                    profile_name,
                )
                / path
            )

        try:
            return (
                path.is_file()
                and path.stat().st_size > 0
            )
        except OSError:
            return False

    @staticmethod
    def _normalize_favicon_homepage(
        homepage,
    ) -> str | None:
        if not isinstance(homepage, str):
            return None

        homepage = homepage.strip()

        if not homepage or " " in homepage:
            return None

        parsed = urllib.parse.urlparse(homepage)

        if not parsed.scheme:
            homepage = f"https://{homepage}"
            parsed = urllib.parse.urlparse(homepage)

        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
        ):
            return None

        return homepage

    def _download_favicon(
        self,
        homepage: str,
    ) -> tuple[bytes, str] | None:
        candidates = self._favicon_candidates(homepage)

        for favicon_url in candidates:
            response_data = self._fetch_url(
                favicon_url
            )

            if response_data is None:
                continue

            content, content_type = response_data

            if not self._is_favicon_payload(
                favicon_url,
                content,
                content_type,
            ):
                continue

            return (
                content,
                self._favicon_extension(
                    favicon_url,
                    content_type,
                ),
            )

        return None

    @staticmethod
    def _is_favicon_payload(
        favicon_url: str,
        content: bytes,
        content_type: str,
    ) -> bool:
        """Evita persistir uma página HTML como se fosse um favicon."""
        if (
            not content
            or "text/html" in content_type.lower()
        ):
            return False

        if content.startswith(
            (
                b"<!DOCTYPE",
                b"<html",
                b"<HTML",
            )
        ):
            return False

        if content.startswith(
            b"\x89PNG\r\n\x1a\n"
        ):
            return True

        if content.startswith(
            b"\xff\xd8\xff"
        ):
            return True

        if content.startswith(
            (
                b"GIF87a",
                b"GIF89a",
                b"RIFF",
            )
        ):
            return True

        if content[:4] == b"\x00\x00\x01\x00":
            return True

        return any(
            marker in content_type.lower()
            for marker in (
                "image/",
                "icon",
            )
        )

    def _favicon_candidates(
        self,
        homepage: str,
    ) -> list[str]:
        parsed = urllib.parse.urlparse(homepage)

        origin = (
            f"{parsed.scheme}://{parsed.netloc}"
        )

        candidates = []

        response_data = self._fetch_url(
            homepage
        )

        html = (
            response_data[0].decode(
                "utf-8",
                errors="ignore",
            )
            if response_data
            else ""
        )

        if html:
            parser = FaviconLinkParser()

            try:
                parser.feed(html)
            except Exception:
                pass

            for href in parser.hrefs:
                candidates.append(
                    urllib.parse.urljoin(
                        homepage,
                        href,
                    )
                )

        candidates.extend(
            [
                urllib.parse.urljoin(
                    origin,
                    "/favicon.ico",
                ),
                (
                    "https://www.google.com/s2/favicons"
                    f"?domain={urllib.parse.quote(parsed.netloc)}"
                    "&sz=64"
                ),
            ]
        )

        deduped = []
        seen = set()

        for url in candidates:
            if url not in seen:
                deduped.append(url)
                seen.add(url)

        return deduped

    def _fetch_url(
        self,
        url: str,
    ) -> tuple[bytes, str] | None:
        for attempt in range(
            FAVICON_RETRIES + 1
        ):
            try:
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "NaveHub/1.4"
                    },
                )

                with urllib.request.urlopen(
                    request,
                    timeout=FAVICON_REQUEST_TIMEOUT,
                ) as response:
                    content = response.read(
                        FAVICON_MAX_BYTES
                    )
                    content_type = (
                        response.headers.get(
                            "Content-Type",
                            "",
                        )
                    )

                return (
                    content,
                    content_type,
                )

            except (
                OSError,
                urllib.error.URLError,
                http.client.HTTPException,
                ValueError,
            ):
                if attempt >= FAVICON_RETRIES:
                    return None

                time.sleep(
                    0.4 * (attempt + 1)
                )

        return None

    @staticmethod
    def _favicon_extension(
        favicon_url: str,
        content_type: str,
    ) -> str:
        content_type = content_type.lower()

        if "png" in content_type:
            return ".png"

        if (
            "jpeg" in content_type
            or "jpg" in content_type
        ):
            return ".jpg"

        suffix = Path(
            urllib.parse.urlparse(
                favicon_url
            ).path
        ).suffix.lower()

        if suffix in {
            ".ico",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
        }:
            return (
                ".jpg"
                if suffix == ".jpeg"
                else suffix
            )

        return ".ico"

    def ensure_v14_accounts(self):
        self._remove_legacy_static_platform_dirs()

        created_names = []

        for display_name, homepage in (
            V14_STATIC_PLATFORM_ACCOUNTS
        ):
            if self._create_seed_profile(
                STATIC_PLATFORM,
                display_name,
                homepage,
            ):
                created_names.append(
                    display_name
                )

        if created_names:
            self._append_profiles_to_order(
                STATIC_PLATFORM,
                created_names,
            )

        # Importante:
        # nunca substitui uma ordem que já foi definida pelo usuário.
        self._sync_static_platform_order()

        try:
            (
                self.base_dir / V14_SEED_MARKER
            ).touch(exist_ok=True)
        except OSError as error:
            print(
                "Aviso: não foi possível registrar "
                f"contas v1.4: {error}"
            )

    def _remove_legacy_static_platform_dirs(self):
        for platform in LEGACY_STATIC_PLATFORMS:
            legacy_dir = (
                self.base_dir
                / platform.lower().replace(" ", "")
            )

            current_dir = (
                self.base_dir
                / STATIC_PLATFORM.lower().replace(" ", "")
            )

            if (
                legacy_dir == current_dir
                or not legacy_dir.exists()
            ):
                continue

            try:
                shutil.rmtree(legacy_dir)
            except OSError as error:
                print(
                    "Aviso: não foi possível remover "
                    f"categoria antiga {platform}: {error}"
                )

    def _expected_static_profile_names(self) -> list[str]:
        return [
            self.get_profile_dir(
                STATIC_PLATFORM,
                display_name,
            ).name
            for display_name, _homepage
            in V14_STATIC_PLATFORM_ACCOUNTS
        ]

    def _sync_static_platform_order(self):
        """
        Sincroniza a lista de contas sem destruir a ordem manual.

        Regras:
        - Se já existe navehub_order.json, sua ordem é preservada.
        - Contas que não existem mais são removidas da ordem.
        - Contas novas do seed entram no final.
        - Contas criadas manualmente também são preservadas.
        - Somente quando não existe uma ordem salva é criada a ordem inicial.
        """
        expected = self._expected_static_profile_names()

        existing = {
            directory.name.lower(): directory.name
            for directory in self.get_platform_dir(
                STATIC_PLATFORM
            ).iterdir()
            if directory.is_dir()
        }

        current_order = self._read_profile_order(
            STATIC_PLATFORM
        )

        if current_order:
            order = []
            seen = set()

            # 1. Preserva a ordem escolhida pelo usuário.
            for name in current_order:
                actual = existing.get(
                    name.lower()
                )

                if (
                    actual
                    and actual.lower() not in seen
                ):
                    order.append(actual)
                    seen.add(actual.lower())

            # 2. Contas novas do seed entram no final.
            for name in expected:
                actual = existing.get(
                    name.lower()
                )

                if (
                    actual
                    and actual.lower() not in seen
                ):
                    order.append(actual)
                    seen.add(actual.lower())

            # 3. Contas criadas manualmente também ficam.
            for name in existing.values():
                if name.lower() not in seen:
                    order.append(name)
                    seen.add(name.lower())

        else:
            # Primeira criação da ordem.
            order = [
                existing[name.lower()]
                for name in expected
                if name.lower() in existing
            ]

            seen = {
                name.lower()
                for name in order
            }

            # Preserva contas manuais já existentes.
            for name in existing.values():
                if name.lower() not in seen:
                    order.append(name)
                    seen.add(name.lower())

        self.save_profile_order(
            STATIC_PLATFORM,
            order,
        )

    def _create_seed_profile(
        self,
        platform: str,
        display_name: str,
        homepage: str | None,
    ) -> bool:
        """
        Cria/atualiza uma conta de seed sem sobrescrever
        configurações personalizadas já existentes.
        """
        profile_dir = self.get_profile_dir(
            platform,
            display_name,
        )

        created = not profile_dir.exists()

        profile_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = self._read_profile_data(
            platform,
            display_name,
        )

        # CORREÇÃO:
        # Antes o seed executava sempre:
        #
        #     data["display_name"] = display_name
        #
        # Isso apagava a legenda personalizada na próxima abertura.
        #
        # Agora só cria o valor padrão se ainda não houver
        # uma legenda salva.
        current_display_name = data.get(
            "display_name"
        )

        if (
            not isinstance(
                current_display_name,
                str,
            )
            or not current_display_name.strip()
        ):
            data["display_name"] = display_name

        # Não sobrescreve homepage personalizada.
        if homepage and not data.get("homepage"):
            data["homepage"] = homepage

        elif (
            platform != STATIC_PLATFORM
            and not data.get("homepage")
        ):
            default_homepage = (
                self.get_default_homepage(
                    platform
                )
            )

            if default_homepage:
                data["homepage"] = default_homepage

        self._write_profile_data(
            platform,
            display_name,
            data,
        )

        return created

    def _append_profiles_to_order(
        self,
        platform: str,
        profile_names: list[str],
    ):
        new_storage_names = [
            self.get_profile_dir(
                platform,
                name,
            ).name
            for name in profile_names
        ]

        new_keys = {
            name.lower()
            for name in new_storage_names
        }

        order = self._read_profile_order(
            platform
        )

        if not order:
            order = [
                directory.name
                for directory in self.get_platform_dir(
                    platform
                ).iterdir()
                if (
                    directory.is_dir()
                    and directory.name.lower()
                    not in new_keys
                )
            ]

        seen = {
            name.lower()
            for name in order
        }

        for storage_name in new_storage_names:
            if storage_name.lower() not in seen:
                order.append(storage_name)
                seen.add(storage_name.lower())

        self.save_profile_order(
            platform,
            order,
        )

    def mark_as_accessed(
        self,
        platform: str,
        profile_name: str,
    ):
        """Registra o acesso apenas nas plataformas com status diário."""
        if platform == STATIC_PLATFORM:
            return

        data = self._read_profile_data(
            platform,
            profile_name,
        )

        data["last_access"] = date.today().isoformat()

        self._write_profile_data(
            platform,
            profile_name,
            data,
        )

    def get_profile_status(
        self,
        platform: str,
        profile_name: str,
    ) -> str:
        # Legalizadas não têm status vinculado ao dia ou ao acesso.
        if platform == STATIC_PLATFORM:
            return "A"

        data = self._read_profile_data(
            platform,
            profile_name,
        )

        last_access = data.get(
            "last_access"
        )

        if (
            last_access
            == date.today().isoformat()
        ):
            return "A"

        return "B"

    def reset_profile_statuses(
        self,
        platform: str,
    ) -> int:
        """
        Restaura todas as contas da plataforma ao estado B.

        O reset remove apenas o registro de acesso do dia.
        Cookies, login, site configurado e ordem manual
        das contas não são alterados.
        """
        if platform == STATIC_PLATFORM:
            return 0

        changed = 0

        for profile_name in self.list_profiles(
            platform
        ):
            data = self._read_profile_data(
                platform,
                profile_name,
            )

            if "last_access" not in data:
                continue

            data.pop(
                "last_access",
                None,
            )

            self._write_profile_data(
                platform,
                profile_name,
                data,
            )

            changed += 1

        return changed

    def get_window_size(self) -> tuple[int, int]:
        """Retorna um tamanho inicial adequado à tela disponível."""

        def positive_int(value, default):
            try:
                size = int(value)
            except (
                TypeError,
                ValueError,
            ):
                return default

            return (
                size
                if size > 0
                else default
            )

        width = 500
        height = 900

        return (
            width,
            height,
        )

    def set_window_position(
        self,
        x: int,
        y: int,
    ):
        """Define a posição da próxima janela de conta nesta execução."""
        self.window_position = (
            max(0, int(x)),
            max(0, int(y)),
        )

    def get_window_position(
        self,
    ) -> tuple[int, int] | None:
        """Retorna a posição calculada pela janela principal, se houver."""
        return getattr(
            self,
            "window_position",
            None,
        )

    def get_browser_app_id(
        self,
        platform: str,
    ) -> str:
        """Identificador da janela do Chrome usado pelo gerenciador gráfico."""
        safe_platform = re.sub(
            r"[^a-z0-9]+",
            "-",
            platform.lower(),
        ).strip("-")

        return (
            f"navehub-{safe_platform or 'conta'}"
        )

    def get_browser_icon_path(
        self,
        platform: str,
    ) -> Path:
        """
        Ícone exibido pelo sistema para a janela de uma conta.

        Para as plataformas com status diário, a janela usa o ícone B.
        Legalizadas não possui estado B, então preserva seu ícone próprio.
        """
        project_dir = (
            Path(__file__).resolve().parent.parent
        )

        if platform == STATIC_PLATFORM:
            return (
                project_dir
                / "icons"
                / "accounts"
                / "outras.png"
            )

        safe_platform = (
            platform.lower().replace(" ", "")
        )

        return (
            project_dir
            / "icons"
            / "accounts"
            / f"{safe_platform}_b.webp"
        )

    def ensure_browser_desktop_entry(
        self,
        platform: str,
        browser: str,
    ) -> str:
        """
        Registra o ícone da janela Chrome no menu/dock do Linux.
        """
        app_id = self.get_browser_app_id(
            platform
        )

        icon_path = self.get_browser_icon_path(
            platform
        )

        desktop_dir = (
            Path.home()
            / ".local"
            / "share"
            / "applications"
        )

        desktop_file = (
            desktop_dir
            / f"{app_id}.desktop"
        )

        platform_name = (
            platform
            .replace("\n", " ")
            .replace("\r", " ")
        )

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
            desktop_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            if (
                not desktop_file.exists()
                or desktop_file.read_text(
                    encoding="utf-8"
                ) != contents
            ):
                desktop_file.write_text(
                    contents,
                    encoding="utf-8",
                )

        except OSError as e:
            print(
                "Aviso: não foi possível registrar "
                f"o ícone da janela: {e}"
            )

        return app_id

    def get_platform_status(
        self,
        platform: str,
    ) -> str:
        if platform == STATIC_PLATFORM:
            return "A"

        profiles = self.list_profiles(
            platform
        )

        if not profiles:
            return "B"

        for profile_name in profiles:
            if (
                self.get_profile_status(
                    platform,
                    profile_name,
                )
                == "B"
            ):
                return "B"

        return "A"

    def _reserve_local_port(self) -> int:
        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        ) as sock:
            sock.bind(
                ("127.0.0.1", 0)
            )

            return sock.getsockname()[1]

    def _cleanup_cdp_popup_blockers(self):
        for (
            profile_dir,
            session,
        ) in list(
            self._cdp_popup_blockers.items()
        ):
            if (
                not session.is_alive()
                or not self._profile_is_running(
                    profile_dir
                )
            ):
                session.stop()

                self._cdp_popup_blockers.pop(
                    profile_dir,
                    None,
                )

    def launch_profile(
        self,
        platform: str,
        profile_name: str,
    ):
        launch_key = (
            platform,
            profile_name,
        )

        now = time.monotonic()

        last_launch = self._last_launch_at.get(
            launch_key
        )

        if (
            last_launch is not None
            and now - last_launch
            < LAUNCH_DEBOUNCE_SECONDS
        ):
            return True

        browser = self.config.get(
            "browser",
            "google-chrome",
        )

        if platform == STATIC_PLATFORM:
            homepage = self.get_profile_homepage(
                platform,
                profile_name,
            )

            cmd = [
                browser,
                "--new-window",
                "--start-fullscreen",
                homepage,
            ]

            try:
                subprocess.Popen(cmd)
            except FileNotFoundError:
                return False

            self._last_launch_at[
                launch_key
            ] = now

            return True

        profile_dir = self.create_profile(
            platform,
            profile_name,
        )

        homepage = self.get_profile_homepage(
            platform,
            profile_name,
        )

        window_width, window_height = (
            self.get_window_size()
        )

        window_position = (
            self.get_window_position()
        )

        app_id = (
            self.ensure_browser_desktop_entry(
                platform,
                browser,
            )
        )

        title_source = build_page_title_source(
            self.get_profile_display_name(
                platform,
                profile_name,
            )
        )

        popup_blocker_class = {
            "8U": EightUPopupBlockerSession,
            "777": SevenSevenPopupBlockerSession,
            "365GG": ThreeSixtyFiveGGPopupBlockerSession,
            "93H": NinetyThreeHPopupBlockerSession,
        }.get(platform)

        cdp_port = self._reserve_local_port()

        cmd = [
            browser,
            f"--user-data-dir={profile_dir}",
            *(
                [
                    f"--remote-debugging-port={cdp_port}",
                    "--remote-debugging-address=127.0.0.1",
                ]
                if cdp_port is not None
                else []
            ),
            "--no-first-run",
            "--no-default-browser-check",
            "--ozone-platform=x11",
            f"--class={app_id}",
            f"--window-size={window_width},{window_height}",
            *(
                [
                    "--window-position="
                    f"{window_position[0]},"
                    f"{window_position[1]}"
                ]
                if window_position is not None
                else []
            ),
            f"--app={homepage}",
        ]

        try:
            process = subprocess.Popen(cmd)
        except FileNotFoundError:
            return False

        self._cleanup_cdp_popup_blockers()

        session = (
            popup_blocker_class(
                process,
                profile_dir,
                cdp_port,
                title_source,
            )
            if popup_blocker_class is not None
            else NaveHubTitleSession(
                process,
                profile_dir,
                cdp_port,
                title_source,
            )
        )

        self._cdp_popup_blockers[
            profile_dir
        ] = session

        session.start()

        self._schedule_autoclean_after_close(
            process,
            platform,
            profile_name,
            profile_dir,
            now,
        )

        self._last_launch_at[
            launch_key
        ] = now

        self.mark_as_accessed(
            platform,
            profile_name,
        )

        return True

    def _schedule_autoclean_after_close(
        self,
        process: subprocess.Popen,
        platform: str,
        profile_name: str,
        profile_dir: Path,
        launched_at: float,
    ):
        """Executa o AutoClean somente após o Chrome liberar o perfil."""
        thread = threading.Thread(
            target=self._wait_for_profile_close_and_clean,
            args=(
                process,
                platform,
                profile_name,
                profile_dir,
                launched_at,
            ),
            daemon=True,
        )

        thread.start()

    def _wait_for_profile_close_and_clean(
        self,
        process: subprocess.Popen,
        platform: str,
        profile_name: str,
        profile_dir: Path,
        launched_at: float,
    ):
        try:
            process.wait()
        except OSError as error:
            print(
                "Aviso: não foi possível aguardar "
                f"fechamento da conta: {error}"
            )
            return

        observed_running = (
            time.monotonic() - launched_at
            >= 2
        )

        if not observed_running:
            wait_until = (
                time.monotonic() + 10
            )

            while time.monotonic() < wait_until:
                if self._profile_is_running(
                    profile_dir
                ):
                    observed_running = True
                    break

                time.sleep(0.2)

        stable_closed_checks = 0

        while (
            observed_running
            and stable_closed_checks < 2
        ):
            if self._profile_is_running(
                profile_dir
            ):
                stable_closed_checks = 0
            else:
                stable_closed_checks += 1

            time.sleep(0.5)

        session = self._cdp_popup_blockers.pop(
            profile_dir,
            None,
        )

        if session is not None:
            session.stop()

        self.autoclean.clean(
            profile_dir,
            platform=platform,
            profile_name=profile_name,
        )

    @staticmethod
    def _profile_is_running(
        profile_dir: Path,
    ) -> bool:
        """Verifica se ainda existe Chrome usando este perfil."""
        lock = profile_dir / "SingletonLock"

        if (
            not lock.exists()
            and not lock.is_symlink()
        ):
            return False

        try:
            target = (
                os.readlink(lock)
                if lock.is_symlink()
                else ""
            )
        except OSError:
            return True

        if "-" in target:
            pid_text = target.rsplit(
                "-",
                1,
            )[-1]

            if pid_text.isdigit():
                try:
                    os.kill(
                        int(pid_text),
                        0,
                    )
                    return True
                except OSError:
                    return False

        return True

    def rename_profile(
        self,
        platform: str,
        old_name: str,
        new_name: str,
    ) -> bool:
        old_dir = self.get_profile_dir(
            platform,
            old_name,
        )

        new_dir = self.get_profile_dir(
            platform,
            new_name,
        )

        if (
            old_dir.exists()
            and not new_dir.exists()
        ):
            old_dir.rename(new_dir)

            self._replace_in_profile_order(
                platform,
                old_name,
                new_name,
            )

            return True

        return False

    def delete_profile(
        self,
        platform: str,
        profile_name: str,
    ) -> bool:
        profile_dir = self.get_profile_dir(
            platform,
            profile_name,
        )

        if profile_dir.exists():
            shutil.rmtree(profile_dir)

            self._remove_from_profile_order(
                platform,
                profile_name,
            )

            return True

        return False

    def clone_profile(
        self,
        platform: str,
        profile_name: str,
    ) -> str | None:
        source_dir = self.get_profile_dir(
            platform,
            profile_name,
        )

        if not source_dir.exists():
            return None

        clone_name = self._unique_profile_name(
            platform,
            profile_name,
        )

        clone_dir = self.get_profile_dir(
            platform,
            clone_name,
        )

        try:
            shutil.copytree(
                source_dir,
                clone_dir,
                ignore=shutil.ignore_patterns(
                    *CHROME_RUNTIME_FILES
                ),
                symlinks=True,
            )
        except OSError:
            if clone_dir.exists():
                shutil.rmtree(
                    clone_dir,
                    ignore_errors=True,
                )

            return None

        order = self._read_profile_order(
            platform
        )

        if order:
            inserted = []
            source_key = profile_name.lower()
            added = False

            for name in order:
                inserted.append(name)

                if name.lower() == source_key:
                    inserted.append(
                        clone_name
                    )
                    added = True

            if not added:
                inserted.append(
                    clone_name
                )

            self.save_profile_order(
                platform,
                inserted,
            )

        return clone_name

    def heavy_clean_profile(
        self,
        platform: str,
        profile_name: str,
    ) -> bool:
        profile_dir = self.get_profile_dir(
            platform,
            profile_name,
        )

        if not profile_dir.exists():
            return False

        settings = self._read_profile_data(
            platform,
            profile_name,
        )

        visual_settings = {
            key: value
            for key, value in settings.items()
            if key in VISUAL_IDENTITY_KEYS
        }

        try:
            shutil.rmtree(profile_dir)

            profile_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._write_profile_data(
                platform,
                profile_name,
                visual_settings,
            )

        except OSError:
            return False

        return True

    def list_profiles(
        self,
        platform: str,
    ) -> list:
        platform_dir = self.get_platform_dir(
            platform
        )

        if not platform_dir.exists():
            return []

        profiles = [
            d.name
            for d in platform_dir.iterdir()
            if d.is_dir()
        ]

        if platform != "8U":
            default_order = sorted(
                profiles
            )
        else:
            def eight_u_sort_key(
                profile_name: str,
            ):
                vip_match = re.search(
                    r"vip(\d+)$",
                    profile_name,
                    re.IGNORECASE,
                )

                vip_level = (
                    int(vip_match.group(1))
                    if vip_match
                    else -1
                )

                return (
                    -vip_level,
                    profile_name.lower(),
                )

            default_order = sorted(
                profiles,
                key=eight_u_sort_key,
            )

        by_key = {
            name.lower(): name
            for name in profiles
        }

        saved_order = self._read_profile_order(
            platform
        )

        ordered = []
        seen = set()

        # Primeiro restaura exatamente a ordem salva.
        for name in saved_order:
            key = name.lower()
            actual = by_key.get(key)

            if (
                actual
                and key not in seen
            ):
                ordered.append(actual)
                seen.add(key)

        # Depois acrescenta qualquer conta que exista
        # mas ainda não esteja no arquivo de ordem.
        ordered.extend(
            name
            for name in default_order
            if name.lower() not in seen
        )

        return ordered