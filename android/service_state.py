"""File-based IPC state shared by the activity and foreground service."""

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4


class ServiceState:
    """Keep service state in fixed files below an app-private directory."""

    CONFIG_FILE = "monitor.json"
    STOP_FILE = "monitor.stop"
    TIMEOUT_FILE = "monitor.timeout"
    TIMEOUT_CLAIM_PREFIX = ".monitor.timeout.ack."
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
        self.timeout_path = self.base_dir / self.TIMEOUT_FILE
        self.events_path = self.base_dir / self.EVENT_FILE

    def write_config(self, config):
        """Atomically replace monitor configuration and clear a prior stop request."""
        if not isinstance(config, Mapping):
            raise TypeError("config must be a mapping")
        payload = json.dumps(dict(config), ensure_ascii=False, separators=(",", ":"))
        self._replace_text(self.config_path, f"{payload}\n")
        self.clear_stop()
        self.clear_timeout()

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

    def request_timeout(self, token=None):
        """Atomically create the marker also written by the generated Java service."""
        token = str(token or uuid4()).strip()
        if not token or "\n" in token or "\r" in token:
            raise ValueError("timeout token must be one non-empty line")
        self._replace_text(self.timeout_path, f"{token}\n")
        return token

    def _timeout_claim_paths(self):
        return sorted(
            path
            for path in self.base_dir.glob(f"{self.TIMEOUT_CLAIM_PREFIX}*")
            if path.is_file()
        )

    @staticmethod
    def _read_timeout_path(path):
        try:
            token = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return None
        return token or None

    def read_timeout_token(self):
        """Read pending timeout evidence without deleting it."""
        for path in (self.timeout_path, *self._timeout_claim_paths()):
            token = self._read_timeout_path(path)
            if token is not None:
                return token
        return None

    def clear_timeout(self):
        """Remove a stale Android foreground-service timeout marker."""
        for path in (self.timeout_path, *self._timeout_claim_paths()):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def timeout_requested(self):
        return self.timeout_path.is_file() or bool(self._timeout_claim_paths())

    def _timeout_claim_path(self, expected_token):
        digest = hashlib.sha256(str(expected_token).encode("utf-8")).hexdigest()
        return self.base_dir / f"{self.TIMEOUT_CLAIM_PREFIX}{digest}"

    def ack_timeout(self, expected_token):
        """Delete only timeout evidence whose content matches expected_token."""
        expected_token = str(expected_token)
        for claim_path in self._timeout_claim_paths():
            if self._read_timeout_path(claim_path) != expected_token:
                continue
            try:
                claim_path.unlink()
            except FileNotFoundError:
                pass
            return True

        claim_path = self._timeout_claim_path(expected_token)
        if claim_path.exists():
            return False
        try:
            os.replace(self.timeout_path, claim_path)
        except FileNotFoundError:
            return False
        if self._read_timeout_path(claim_path) != expected_token:
            return False
        try:
            claim_path.unlink()
        except FileNotFoundError:
            pass
        return True

    def append_event(self, event):
        """Append one compact JSON event while retaining only recent log lines."""
        if not isinstance(event, Mapping):
            raise TypeError("event must be a mapping")
        line = json.dumps(dict(event), ensure_ascii=False, separators=(",", ":")) + "\n"
        try:
            existing_lines = self.events_path.read_text(encoding="utf-8").split("\n")
        except FileNotFoundError:
            existing_lines = []
        except UnicodeError:
            self._replace_text(self.events_path, line)
            return

        if existing_lines and existing_lines[-1] == "":
            existing_lines.pop()

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
            lines = self.events_path.read_text(encoding="utf-8").split("\n")
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
