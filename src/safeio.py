"""Atomic no-clobber results and allow-listed telemetry, not raw provider logs."""
import json
import os
from pathlib import Path
import re
import tempfile

from .protocol import ProtocolError, strict_json


def scratch_directory():
    path = Path(__file__).resolve().parents[1] / ".local" / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path, max_bytes=1048576):
    with Path(path).open("rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ProtocolError("file_size_limit")
    try:
        return strict_json(data.decode("utf-8-sig"))
    except UnicodeError as exc:
        raise ProtocolError("invalid_utf8") from exc


def write_json(path, value):
    """Link a complete temp file into place; never overwrite existing evidence."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".pending-", delete=False) as handle:
            name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "nt":
            # Windows rename is atomic and fails if destination exists; hardlinks may be
            # prohibited by managed filesystems even when normal writes are allowed.
            os.rename(name, path)
        else:
            os.link(name, path)
    finally:
        if name:
            Path(name).unlink(missing_ok=True)


_PRIVATE = [
    (re.compile(r"(?i)\b(?:sk|sess)-[A-Za-z0-9_-]{8,}"), "[REDACTED_SECRET]"),
    (re.compile(r"(?i)\bBearer\s+\S+"), "[REDACTED_AUTH]"),
    (re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
    (re.compile(r"[A-Za-z]:[\\/][^\s\"<>]+"), "[REDACTED_PATH]"),
    (re.compile(r"/(?:Users|home)/[^\s\"<>]+"), "[REDACTED_PATH]"),
]


def public_export(value):
    """Input must already be application-owned fields, not arbitrary provider JSON."""
    if isinstance(value, dict):
        return {k: public_export(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [public_export(v) for v in value]
    if isinstance(value, str):
        for pattern, replacement in _PRIVATE:
            value = pattern.sub(replacement, value)
    return value
