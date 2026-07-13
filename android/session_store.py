"""Private on-device storage for the exported login cookie."""

import os
import tempfile
from pathlib import Path


class SessionStore:
    """Persist the cookie only beneath the application-private directory."""

    COOKIE_FILE = "cookie.txt"

    def __init__(self, base_dir):
        self.base_dir = Path(base_dir).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.base_dir = self.base_dir.resolve()
        if not self.base_dir.is_dir():
            raise ValueError("base_dir must be a directory")
        self.cookie_path = self.base_dir / self.COOKIE_FILE

    def load_cookie(self):
        """Return an empty string when no valid saved session is available."""
        try:
            return self.cookie_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return ""

    def save_cookie(self, cookie):
        """Atomically replace the saved UTF-8 cookie."""
        if not isinstance(cookie, str):
            raise TypeError("cookie must be a string")
        self._replace_text(self.cookie_path, cookie)

    def clear(self):
        """Forget the saved session without treating an absent file as an error."""
        try:
            self.cookie_path.unlink()
        except FileNotFoundError:
            pass

    def _replace_text(self, path, content):
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.base_dir,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_file.write(content)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_path = Path(temp_file.name)
            temp_path.replace(path)
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
