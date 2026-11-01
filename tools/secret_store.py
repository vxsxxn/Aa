"""Secret store — a small vault for API keys, separate from the browser login vault.

Two backends, tried in order:
  1. OS keychain (``keyring``) — Windows Credential Manager / macOS Keychain / libsecret.
     Nothing sensitive ever touches disk in plaintext.
  2. Fallback: Fernet-encrypted file under the profile dir, key in a separate
     ``.vaultkey`` file (chmod 600). Clearly labeled second-best — no keychain, e.g.
     a headless Linux box or WSL without a secret service.

Storage layout (keyring): service ``aa-agent``, account ``<name>``.
Layout (file): ``<profile>/secrets.enc`` (Fernet tokens, one per line, JSON payload)
             + ``<profile>/secrets.key`` (random 32-byte key, chmod 600).

API:
  get(name) -> str | None
  set(name, value) -> None
  delete(name) -> None
  list_names() -> [str]
  backend() -> "keychain" | "file" | "none"
"""

import base64
import json
import os
import stat
import sys
import threading
from pathlib import Path
from typing import List, Optional

_logger = __import__("logging").getLogger(__name__)

_SERVICE = "aa-agent"
_lock = threading.Lock()


# --- Keychain backend -------------------------------------------------------

def _keychain():
    try:
        import keyring  # type: ignore
    except Exception:
        return None
    try:
        backend = keyring.get_keyring()
        # A fail/chainer with no usable primary means no OS secret service.
        module = type(backend).__module__
        if "fail" in module.lower() or "null" in module.lower():
            return None
        return keyring
    except Exception:
        return None


# --- File backend -----------------------------------------------------------

def _profile_dir() -> Path:
    root = os.environ.get("HERMES_HOME") or os.environ.get("AA_HOME")
    if root:
        return Path(root)
    return Path.home() / ".aa"


def _file_paths() -> tuple:
    d = _profile_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "secrets.enc", d / "secrets.key"


def _load_or_create_file_key(key_path: Path) -> bytes:
    if key_path.exists():
        return key_path.read_bytes()
    key = base64.urlsafe_b64encode(os.urandom(32))
    key_path.write_bytes(key)
    try:
        key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
    except OSError:
        pass
    return key


def _read_file_store() -> dict:
    enc_path, key_path = _file_paths()
    if not enc_path.exists():
        return {}
    from cryptography.fernet import Fernet
    f = Fernet(_load_or_create_file_key(key_path))
    out = {}
    for line in enc_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.update(json.loads(f.decrypt(line.encode()).decode()))
        except Exception:
            continue  # a torn/corrupt line shouldn't kill the whole store
    return out


def _write_file_store(data: dict) -> None:
    from cryptography.fernet import Fernet
    enc_path, key_path = _file_paths()
    f = Fernet(_load_or_create_file_key(key_path))
    lines = [f.encrypt(json.dumps({k: v}).encode()).decode() for k, v in data.items()]
    tmp = enc_path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(enc_path)


# --- Public API -------------------------------------------------------------

def backend() -> str:
    if _keychain() is not None:
        return "keychain"
    return "file"


def get(name: str) -> Optional[str]:
    name = str(name).strip()
    if not name:
        return None
    with _lock:
        kc = _keychain()
        if kc is not None:
            try:
                val = kc.get_password(_SERVICE, name)
                if val is not None:
                    return val
            except Exception as e:
                _logger.debug("keychain get failed for %s: %s", name, e)
        return _read_file_store().get(name)


def set(name: str, value: str) -> None:
    name, value = str(name).strip(), str(value)
    if not name or not value:
        raise ValueError("secret name and value must be non-empty")
    with _lock:
        kc = _keychain()
        if kc is not None:
            kc.set_password(_SERVICE, name, value)
            return
        data = _read_file_store()
        data[name] = value
        _write_file_store(data)


def delete(name: str) -> bool:
    name = str(name).strip()
    if not name:
        return False
    with _lock:
        kc = _keychain()
        if kc is not None:
            try:
                kc.delete_password(_SERVICE, name)
                return True
            except Exception:
                pass  # not present in keychain; try the file store
        data = _read_file_store()
        if name in data:
            del data[name]
            _write_file_store(data)
            return True
    return False


def list_names() -> List[str]:
    names: List[str] = []
    with _lock:
        kc = _keychain()
        if kc is not None:
            try:
                # keyring has no cross-backend listing; only enumerate the file store
                # and let the caller use `get` to probe named keychain entries.
                pass
            except Exception:
                pass
        names = sorted(_read_file_store().keys())
    return names


if __name__ == "__main__":  # quick manual check: python -m tools.secret_store get NAME
    cmd, name = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""
    if cmd == "get":
        v = get(name)
        print(v[:4] + "..." if v else "(not set)")
    elif cmd == "set":
        set(name, sys.stdin.read().strip())
        print("stored")
    elif cmd == "delete":
        print("deleted" if delete(name) else "not found")
    elif cmd == "backend":
        print(backend())
