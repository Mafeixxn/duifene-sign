import configparser
import os

CONFIG_FILE = "duifenyi.ini"
DEFAULTS = {
    "INFO": {"cookie": ""},
    "PREF": {"countdown": "10"},
}


class ConfigManager:
    def __init__(self, filename: str = CONFIG_FILE):
        self.filename = filename
        self.config = configparser.ConfigParser()
        self._ensure_file()

    def _ensure_file(self):
        changed = False
        self.config.clear()
        if os.path.exists(self.filename):
            try:
                self.config.read(self.filename, encoding="utf-8")
            except configparser.Error:
                self.config.clear()
                changed = True
        else:
            changed = True

        if self._ensure_defaults():
            changed = True
        if changed:
            self._save()

    def _ensure_defaults(self) -> bool:
        changed = False
        for section, values in DEFAULTS.items():
            if not self.config.has_section(section):
                self.config[section] = {}
                changed = True
            for key, value in values.items():
                if key not in self.config[section]:
                    self.config[section][key] = value
                    changed = True
        return changed

    def _save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            self.config.write(f)

    def load_cookie(self) -> dict[str, str]:
        try:
            self._ensure_file()
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
        self._ensure_defaults()
        self.config["INFO"]["cookie"] = cookie_str
        self._save()

    def clear_cookie(self):
        self._ensure_defaults()
        self.config["INFO"]["cookie"] = ""
        self._save()

    def get_countdown(self) -> int:
        self._ensure_file()
        return self.config.getint("PREF", "countdown", fallback=10)

    def save_countdown(self, seconds: int):
        self._ensure_defaults()
        self.config["PREF"]["countdown"] = str(seconds)
        self._save()
