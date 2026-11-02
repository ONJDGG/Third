"""Bounded owned subprocesses: byte limits, timeout, cancellation, tree cleanup."""
import os
import signal
import subprocess
import tempfile
import threading
import time
from time import sleep as pause

from .base import BudgetExceeded, ModelFailure
from ..safeio import scratch_directory


def clean_environment():
    allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR",
               "USERPROFILE", "HOME", "LOCALAPPDATA", "APPDATA", "CODEX_HOME",
               "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY"}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    return env


def terminate_owned(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass  # Still kill the owned parent below if tree cleanup is unavailable.
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)


def run_process(argv, payload, timeout, max_bytes, cwd=None, env=None):
    """No shell; only this invocation's process tree may be terminated."""
    started = time.monotonic()
    with tempfile.TemporaryFile(dir=scratch_directory()) as output:
        options = {"start_new_session": True} if os.name != "nt" else {
            "creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
        try:
            process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=output,
                                       stderr=subprocess.DEVNULL, cwd=cwd,
                                       env=env if env is not None else clean_environment(), **options)
        except OSError as exc:
            raise ModelFailure("executable_unavailable") from exc

        def write():
            try:
                process.stdin.write(payload)
                process.stdin.close()
            except (OSError, ValueError):
                pass

        writer = threading.Thread(target=write, daemon=True)
        writer.start()
        try:
            while process.poll() is None:
                if time.monotonic() - started >= timeout:
                    raise BudgetExceeded("call_timeout")
                if os.fstat(output.fileno()).st_size > max_bytes:
                    raise ModelFailure("response_size_limit")
                pause(min(0.025, max(0, timeout - (time.monotonic()-started))))
            writer.join(timeout=1)
            output.seek(0)
            data = output.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ModelFailure("response_size_limit")
            return process.returncode, data
        finally:
            terminate_owned(process)
            writer.join(timeout=1)
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
