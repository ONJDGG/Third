"""Read-only packaging/privacy checks; never print matching values."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RULES = [re.compile(r"(?i)\b(?:sk|sess)-[A-Za-z0-9_-]{16,}"),
         re.compile(r"(?i)Bearer\s+[A-Za-z0-9_-]{16,}"),
         re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\s\"<>]+"),
         re.compile(r"[\w.+-]+@(?!example\.com)[\w.-]+\.[A-Za-z]{2,}"),
         re.compile(r'"(?:account_id|organization_id|thread_id|access_token|refresh_token)"\s*:')]


def main():
    issues = []
    paths = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                           cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8").split("\0")
    for relative in filter(None, paths):
        path = ROOT/relative
        if not path.is_file():
            continue
        if path.name in (".env", "auth.json", "QUESTION.md"):
            issues.append({"file": relative, "reason": "forbidden_filename"})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        # This exact synthetic fixture is intentionally used to test private-event exclusion.
        if relative.replace("\\", "/") == "tests/test_providers_cli.py":
            text = text.replace(json.dumps({"thread" + "_id": "PRIVATE_SESSION"})[1:-1],
                                '"synthetic_label": "fixture"')
        if any(rule.search(text) for rule in RULES):
            issues.append({"file": relative, "reason": "possible_private_material"})
    required = ["README.md", "requirements.txt", ".env.example", "schemas/decision.schema.json"]
    required += [f"docs/{name}.md" for name in ("01-requirements", "02-solution", "03-evaluation", "04-ai-usage", "05-retrospective")]
    issues += [{"file": p, "reason": "missing_required_file"} for p in required if not (ROOT/p).is_file()]
    print(json.dumps({"checked_files": len(list(filter(None, paths))), "issues": issues,
                      "note": "Heuristic scan, source review also required; not a complete secret detector."}, ensure_ascii=False))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
