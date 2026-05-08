import configparser
import os

CONFIG_FILE = "duifenyi.ini"


class ConfigManager:
    def __init__(self, filename: str = CONFIG_FILE):
        self.filename = filename
        self.config = configparser.ConfigParser()
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.filename):
            self.config["INFO"] = {"cookie": ""}
            self.config["PREF"] = {"countdown": "10"}
            self._save()

    def _save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            self.config.write(f)

    def load_cookie(self) -> dict[str, str]:
        try:
            self.config.read(self.filename, encoding="utf-8")
            raw = self.config.get("INFO", "cookie", fallback="")
            if not raw:
                return {}
            cookies = {}
            for pair in raw.split("; "):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    cookies[key] = value
            return cookies
        except Exception:
            return {}

    def save_cookie(self, cookie_str: str):
        self.config["INFO"]["cookie"] = cookie_str
        self._save()

    def clear_cookie(self):
        self.config["INFO"]["cookie"] = ""
        self._save()

    def get_countdown(self) -> int:
        self.config.read(self.filename, encoding="utf-8")
        return self.config.getint("PREF", "countdown", fallback=10)

    def save_countdown(self, seconds: int):
        self.config["PREF"]["countdown"] = str(seconds)
        self._save()
