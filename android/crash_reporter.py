"""Small app-private crash reporter shared by the activity and service."""

import os
import re
import sys
import tempfile
import threading
import traceback
from pathlib import Path


CRASH_FILE = "crash.log"
_SECRET_PATTERN = re.compile(
    r"(?i)\b(cookie|session|sid|token)\b(\s*[:=]\s*)([^;\s,\]\}]+)"
)


def _redact(text):
    return _SECRET_PATTERN.sub(r"\1\2<redacted>", str(text))


def _format_crash(exc_type, exc_value, exc_traceback):
    lines = ["Traceback (most recent call last):\n"]
    for frame in traceback.extract_tb(exc_traceback):
        lines.append(
            f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}\n'
        )
    type_name = getattr(exc_type, "__name__", str(exc_type))
    lines.append(f"{type_name}: {exc_value}\n")
    return _redact("".join(lines))


def write_crash(base_dir, exc_type, exc_value, exc_traceback):
    """Atomically replace the latest private crash traceback without locals."""
    base_path = Path(base_dir).expanduser()
    base_path.mkdir(parents=True, exist_ok=True)
    base_path = base_path.resolve()
    report_path = base_path / CRASH_FILE
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=base_path,
            prefix=f".{CRASH_FILE}.",
            suffix=".tmp",
            delete=False,
        ) as report:
            report.write(_format_crash(exc_type, exc_value, exc_traceback))
            report.flush()
            os.fsync(report.fileno())
            temporary = Path(report.name)
        os.replace(temporary, report_path)
        try:
            report_path.chmod(0o600)
        except OSError:
            pass
        return report_path
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def install_crash_hooks(base_dir, sys_module=sys, threading_module=threading):
    """Install delegating process and thread hooks for one private directory."""
    base_path = str(Path(base_dir).expanduser().resolve())
    original_sys_hook = sys_module.excepthook
    original_thread_hook = getattr(threading_module, "excepthook", None)

    def process_hook(exc_type, exc_value, exc_traceback):
        try:
            write_crash(base_path, exc_type, exc_value, exc_traceback)
        finally:
            original_sys_hook(exc_type, exc_value, exc_traceback)

    sys_module.excepthook = process_hook

    if original_thread_hook is not None:
        def thread_hook(args):
            try:
                write_crash(
                    base_path, args.exc_type, args.exc_value, args.exc_traceback
                )
            finally:
                original_thread_hook(args)

        threading_module.excepthook = thread_hook

    return process_hook
