"""Record actual test execution and retrieval measurement."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluate import benchmark
from src.safeio import public_export, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-annotations", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    process = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                             cwd=ROOT, capture_output=True, timeout=120)
    report = {"executed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "python": sys.version.split()[0], "platform": sys.platform,
              "command": "python -m unittest discover -s tests -v", "exit_code": process.returncode,
              "elapsed_seconds": round(time.monotonic()-started, 3),
              "output": (process.stdout+process.stderr).decode("utf-8", errors="replace").splitlines()}
    write_json(args.output/"tests.json", public_export(report))
    write_json(args.output/"retrieval-benchmark.json", benchmark())
    if process.returncode and args.github_annotations:
        safe_lines = public_export(report["output"])
        first = next((i for i, line in enumerate(safe_lines) if line.startswith("======")), 0)
        excerpt = "\n".join(safe_lines[first:])[-20000:]
        escaped = excerpt.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print("::error title=Offline regression failure::" + escaped)
    print(json.dumps({"exit_code": process.returncode, "elapsed_seconds": report["elapsed_seconds"]}))
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
