"""Preferências DoH locais a cada diretório de dados isolado do Chrome."""

import json
import os
import socket
import tempfile
from pathlib import Path

CLOUDFLARE_DOH = {
    "mode": "secure",
    "templates": "https://chrome.cloudflare-dns.com/dns-query",
}


def profile_is_running(profile_dir: Path) -> bool:
    lock = profile_dir / "SingletonLock"
    if not lock.is_symlink():
        return lock.exists()
    try:
        host, pid = os.readlink(lock).rsplit("-", 1)
        if host != socket.gethostname():
            return True
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except (OSError, ValueError):
        return True
    return True


def configure_secure_dns(profile_dir: Path) -> bool:
    """Configura somente perfis fechados. Nunca sobrescreve estado em uso."""
    if profile_is_running(profile_dir):
        return False
    state_file = profile_dir / "Local State"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    if not isinstance(state, dict):
        raise ValueError("Local State inválido; conteúdo preservado")
    existing = state.get("dns_over_https", {})
    if not isinstance(existing, dict):
        raise ValueError("Preferência DNS inválida; conteúdo preservado")
    if all(existing.get(key) == value for key, value in CLOUDFLARE_DOH.items()):
        return True
    state["dns_over_https"] = {**existing, **CLOUDFLARE_DOH}
    profile_dir.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".navehub-dns-", dir=profile_dir)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(state, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        if state_file.exists():
            os.chmod(temporary, state_file.stat().st_mode & 0o777)
        if profile_is_running(profile_dir):
            return False
        os.replace(temporary, state_file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True
