"""File-based IPC state shared by the activity and foreground service."""

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path


class ServiceState:
    """Keep service state in fixed files below an app-private directory."""

    CONFIG_FILE = "monitor.json"
    STOP_FILE = "monitor.stop"
    EVENT_FILE = "monitor-events.jsonl"
    MAX_EVENT_LINES = 200

    def __init__(self, base_dir):
        self.base_dir = Path(base_dir).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.base_dir = self.base_dir.resolve()
        if not self.base_dir.is_dir():
            raise ValueError("base_dir must be a directory")
        self.config_path = self.base_dir / self.CONFIG_FILE
        self.stop_path = self.base_dir / self.STOP_FILE
        self.events_path = self.base_dir / self.EVENT_FILE

    def write_config(self, config):
        """Atomically replace monitor configuration and clear a prior stop request."""
        if not isinstance(config, Mapping):
            raise TypeError("config must be a mapping")
        payload = json.dumps(dict(config), ensure_ascii=False, separators=(",", ":"))
        self._replace_text(self.config_path, f"{payload}\n")
        self.clear_stop()

    def read_config(self):
        """Return the monitor configuration or None when it is unavailable or invalid."""
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return config if isinstance(config, dict) else None

    def request_stop(self):
        """Atomically create the marker observed by the foreground service."""
        self._replace_text(self.stop_path, "stop\n")

    def clear_stop(self):
        """Remove a prior stop marker when starting a replacement monitor."""
        try:
            self.stop_path.unlink()
        except FileNotFoundError:
            pass

    def stop_requested(self):
        return self.stop_path.is_file()

    def append_event(self, event):
        """Append one compact JSON event while retaining only recent log lines."""
        if not isinstance(event, Mapping):
            raise TypeError("event must be a mapping")
        line = json.dumps(dict(event), ensure_ascii=False, separators=(",", ":")) + "\n"
        try:
            existing_lines = self.events_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            existing_lines = []
        except UnicodeError:
            self._replace_text(self.events_path, line)
            return

        if len(existing_lines) >= self.MAX_EVENT_LINES:
            retained_lines = existing_lines[-(self.MAX_EVENT_LINES - 1):]
            self._replace_text(self.events_path, "\n".join(retained_lines + [line.rstrip("\n")]) + "\n")
            return

        with self.events_path.open("a", encoding="utf-8") as event_file:
            event_file.write(line)
            event_file.flush()
            os.fsync(event_file.fileno())

    def read_events(self):
        """Return well-formed object events, skipping incomplete or malformed lines."""
        try:
            lines = self.events_path.read_text(encoding="utf-8").splitlines()
        except (FileNotFoundError, OSError, UnicodeError):
            return []

        events = []
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return events

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
