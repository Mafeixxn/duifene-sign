"""Fail-closed python-for-android hook for Android 15 service timeouts."""

import os
import tempfile
from pathlib import Path


SERVICE_RELATIVE_PATH = Path(
    "src/main/java/org/example/duifene_sign/ServiceMonitor.java"
)
CLASS_DECLARATION = "public class ServiceMonitor extends "
TIMEOUT_SIGNATURE = "public void onTimeout(int startId, int fgsType)"
TIMEOUT_MARKER = '"monitor.timeout"'

TIMEOUT_OVERRIDE = r'''

    @Override
    public void onTimeout(int startId, int fgsType) {
        java.io.File temporary = new java.io.File(
            getFilesDir(), ".monitor.timeout.tmp"
        );
        java.io.File marker = new java.io.File(getFilesDir(), "monitor.timeout");
        try {
            try (java.io.FileOutputStream output =
                     new java.io.FileOutputStream(temporary, false)) {
                output.write("timeout\n".getBytes(java.nio.charset.StandardCharsets.UTF_8));
                output.flush();
                output.getFD().sync();
            }
            android.system.Os.rename(
                temporary.getAbsolutePath(), marker.getAbsolutePath()
            );
            java.io.FileDescriptor directory = android.system.Os.open(
                getFilesDir().getAbsolutePath(),
                android.system.OsConstants.O_RDONLY
                    | android.system.OsConstants.O_DIRECTORY,
                0
            );
            try {
                android.system.Os.fsync(directory);
            } finally {
                android.system.Os.close(directory);
            }
        } catch (Exception exc) {
            android.util.Log.e(
                "ServiceMonitor", "Unable to persist timeout marker", exc
            );
            temporary.delete();
        } finally {
            stopSelf(startId);
        }
    }
'''


def _replace_text(path, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
            temporary = Path(output.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def patch_service_java(java_path):
    """Patch one generated ServiceMonitor.java or abort on an unsafe shape."""
    java_path = Path(java_path)
    if not java_path.is_file():
        raise FileNotFoundError(f"generated service is missing: {java_path}")

    source = java_path.read_text(encoding="utf-8")
    if TIMEOUT_SIGNATURE in source:
        if (
            source.count(TIMEOUT_SIGNATURE) == 1
            and source.count(TIMEOUT_MARKER) == 1
            and TIMEOUT_OVERRIDE.strip() in source
        ):
            return False
        raise RuntimeError("generated service has an unrecognized timeout override")
    if source.count(CLASS_DECLARATION) != 1 or not source.rstrip().endswith("}"):
        raise RuntimeError("generated ServiceMonitor.java has an unexpected shape")

    closing_brace = source.rfind("}")
    patched = source[:closing_brace] + TIMEOUT_OVERRIDE + source[closing_brace:]
    if patched.count(TIMEOUT_SIGNATURE) != 1 or TIMEOUT_MARKER not in patched:
        raise RuntimeError("timeout override verification failed")
    _replace_text(java_path, patched)
    return True


def before_apk_assemble(_toolchain):
    """Run after p4a renders services and before Gradle compiles Java."""
    patch_service_java(Path.cwd() / SERVICE_RELATIVE_PATH)
