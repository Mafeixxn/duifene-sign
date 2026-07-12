"""Foreground monitor entrypoint for python-for-android."""

import json
import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path


SOURCE_DIR = str(Path(__file__).resolve().parents[1])
if SOURCE_DIR not in sys.path:
    sys.path.insert(0, SOURCE_DIR)

from api_client import ApiClient
from service_state import ServiceState
from sign_service import SignService


REQUIRED_MONITOR_FIELDS = ("cookie", "course_id", "class_id", "class_name")


def parse_service_argument(raw_argument):
    """Return a JSON object passed to the generated service, or an empty object."""
    try:
        argument = json.loads(raw_argument or "")
    except (TypeError, json.JSONDecodeError):
        return {}
    return dict(argument) if isinstance(argument, Mapping) else {}


def load_monitor_config(state, raw_argument):
    """Prefer the shared private-state configuration over a launch fallback."""
    config = state.read_config()
    return config if config is not None else parse_service_argument(raw_argument)


def resolve_private_app_dir(context):
    """Resolve the service's app-private files directory without Kivy."""
    return str(Path(str(context.getFilesDir().getAbsolutePath())).resolve())


class StopMarker:
    """Adapt ServiceState's stop marker to SignService's Event-style contract."""

    POLL_SECONDS = 0.25

    def __init__(self, state):
        self.state = state

    def is_set(self):
        return self.state.stop_requested()

    def wait(self, timeout):
        try:
            timeout = max(0.0, float(timeout))
        except (TypeError, ValueError):
            timeout = 0.0

        deadline = time.monotonic() + timeout
        while not self.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(self.POLL_SECONDS, remaining))
        return self.is_set()


def _append_event(state, level, message):
    state.append_event(
        {
            "level": str(level),
            "message": str(message),
            "timestamp": int(time.time()),
        }
    )


def _has_monitor_fields(config):
    if not isinstance(config, Mapping):
        return False
    return all(
        config.get(field) is not None and str(config[field]).strip()
        for field in REQUIRED_MONITOR_FIELDS
    )


def run_monitor(state, raw_argument, api_factory=ApiClient, service_factory=SignService):
    """Create and run the polling engine until its private stop marker appears."""
    if state.stop_requested():
        _append_event(state, "info", "Monitoring stopped before service startup.")
        return

    config = load_monitor_config(state, raw_argument)
    if not _has_monitor_fields(config):
        _append_event(state, "error", "Monitoring configuration is unavailable.")
        return

    api = api_factory(str(config["cookie"]))
    service = service_factory(
        api,
        on_log=lambda level, message: _append_event(state, level, message),
        on_status=lambda running: _append_event(
            state,
            "info",
            "Monitoring started." if running else "Monitoring stopped.",
        ),
    )
    service.configure(
        course_id=config["course_id"],
        class_id=config["class_id"],
        class_name=config["class_name"],
        countdown=config.get("countdown", 10),
    )
    service.run(StopMarker(state))


def _service_context():
    from jnius import autoclass

    return autoclass("org.kivy.android.PythonService").mService


def main():
    """Run under p4a; its generated foreground service owns the notification."""
    raw_argument = os.environ.get("PYTHON_SERVICE_ARGUMENT", "")
    state = ServiceState(resolve_private_app_dir(_service_context()))
    try:
        run_monitor(state, raw_argument)
    except Exception as exc:
        _append_event(state, "error", f"Monitoring service failed: {exc}")


if __name__ == "__main__":
    main()
