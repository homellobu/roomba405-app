import base64
import json
import os
import time
from pathlib import Path

CONFIG_DIR = Path.home() / ".roomba_app"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSION_TTL = 200

_XOR_KEY = "rcv1"


def _wrap(text: str) -> str:
    raw = text.encode()
    return base64.b64encode(
        bytes(b ^ ord(_XOR_KEY[i % len(_XOR_KEY)]) for i, b in enumerate(raw))
    ).decode()


def _unwrap(text: str) -> str:
    raw = base64.b64decode(text.encode())
    return bytes(b ^ ord(_XOR_KEY[i % len(_XOR_KEY)]) for i, b in enumerate(raw)).decode()


class Store:
    def __init__(self, path: Path = CONFIG_FILE):
        self.path = path
        self.data = {}
        if path.exists():
            try:
                self.data = json.loads(path.read_text())
            except json.JSONDecodeError:
                self.data = {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2))
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @property
    def email(self):
        return self.data.get("email")

    @property
    def password(self):
        stored = self.data.get("password")
        return _unwrap(stored) if stored else None

    @property
    def blid(self):
        return self.data.get("blid")

    def set_blid(self, blid: str):
        self.data["blid"] = blid
        self.save()

    def set_credentials(self, email: str, password: str):
        self.data["email"] = email
        self.data["password"] = _wrap(password)
        self.save()

    def cached_session(self):
        session = self.data.get("session")
        if not session:
            return None
        if time.time() - session.get("_at", 0) > SESSION_TTL:
            return None
        return session

    def save_session(self, session: dict):
        cached = dict(session)
        cached["_at"] = int(time.time())
        self.data["session"] = cached
        self.save()

    def forget_session(self):
        self.data.pop("session", None)
        self.save()

    def forget_all(self):
        self.data = {}
        self.save()
