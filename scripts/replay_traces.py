"""Replay saved decisions through the current runtime, NOT a new model evaluation."""
import copy
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.agent import run_agent
from src.evaluate import check
from src.knowledge import Snapshot
from src.safeio import load_json, write_json
from src.tools import Tools


class Replay:
    name, model, is_mock = "replay", "saved-real-decisions-not-a-new-model-run", True

    def __init__(self, saved):
        self.actions = iter(t["decision"] for t in saved["trace"] if "decision" in t)
        self.original_keys = {c["evidence_id"]: (c["document_id"], c["version_date"], c["fragment_id"])
                              for t in saved["trace"] if "result" in t
                              for c in [t["result"].get("evidence")] if c}

    def decide(self, context, budget):
        budget.request()
        action = copy.deepcopy(next(self.actions))
        current = { (c["document_id"], c["version_date"], c["fragment_id"]): c["evidence_id"]
                    for t in context["observations"] if "result" in t
                    for c in [t["result"].get("evidence")] if c}
        def remap(eids):
            return [current[self.original_keys[eid]] for eid in eids]
        action["evidence_ids"] = remap(action["evidence_ids"])
        for claim in action["claims"]:
            claim["evidence_ids"] = remap(claim["evidence_ids"])
        return action


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for spec in load_json(ROOT/"examples/cases/manifest.json"):
        saved = load_json(ROOT/f'examples/live-codex/{spec["name"]}.output.json')
        result = run_agent(load_json(ROOT/spec["input"]),
                           Tools(Snapshot.load(ROOT/f'data/corpora/{spec["corpus"]}.json'), faults=spec.get("faults")), Replay(saved))
        checks = check(result, spec["expected"])
        rows.append({"case": spec["name"], "passed": all(checks.values()), "checks": checks,
                     "source": f'../live-codex/{spec["name"]}.trace.json'})
    report = {"kind": "runtime_compatibility_replay_not_real_model_rerun",
              "passed": sum(r["passed"] for r in rows), "total": len(rows), "records": rows}
    write_json(args.output, report)
    print(json.dumps({"passed": report["passed"], "total": report["total"]}))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
