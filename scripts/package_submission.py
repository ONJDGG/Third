"""Package clean committed source with hashes, excluding .git and ignored local state."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=ROOT/"dist/agent-submission.zip")
    args = p.parse_args()
    if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, check=True).stdout:
        raise SystemExit("Commit the verified source first; package requires a clean worktree.")
    audit = subprocess.run([sys.executable, "scripts/check_release.py"], cwd=ROOT, capture_output=True)
    if audit.returncode:
        raise SystemExit("Release checks failed; no archive created.")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    canonical = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT,
                               capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(canonical), mode="r:") as tree:
        files = {member.name: tree.extractfile(member).read()
                 for member in tree.getmembers() if member.isfile()}
    manifest = {"project": "Enterprise Evidence Agent", "repository": "https://github.com/ONJDGG/Third",
                "commit": commit, "files": {}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            manifest["files"][name] = hashlib.sha256(content).hexdigest()
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
        info = zipfile.ZipInfo("SUBMISSION_MANIFEST.json", date_time=(2026, 1, 1, 0, 0, 0))
        archive.writestr(info, json.dumps(manifest, ensure_ascii=False, indent=2).encode())
    print(json.dumps({"commit": commit, "files": len(manifest["files"]),
                      "archive_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
