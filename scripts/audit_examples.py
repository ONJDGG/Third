"""Audit saved actual outputs against corpus originals and observed read results."""
import argparse
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.knowledge import Snapshot
from src.safeio import load_json, write_json


def audit(directory):
    rows = []
    specs = {s["name"]: s for s in load_json(ROOT/"examples/cases/manifest.json")}
    for path in sorted(directory.glob("*.output.json")):
        name = path.name.removesuffix(".output.json")
        base_name = re.sub(r"-[1-5]$", "", name)
        spec = specs[base_name]
        result = load_json(path)
        snapshot = Snapshot.load(ROOT/f'data/corpora/{spec["corpus"]}.json')
        reads = {t["result"]["evidence"]["evidence_id"]: t["result"]["evidence"]
                 for t in result["trace"] if t.get("type") == "tool_result"
                 and "evidence" in t["result"]}
        issues = []
        for cite in result["citations"]:
            doc = snapshot.get(cite["document_id"], cite["version_date"], ())
            fragment = next((f for f in doc.fragments if f.fragment_id == cite["fragment_id"]), None) if doc else None
            if not fragment or fragment.text != cite["quote"]:
                issues.append("source_quote_mismatch")
            if cite["evidence_id"] not in reads or reads[cite["evidence_id"]]["quote"] != cite["quote"]:
                issues.append("not_observed_read")
            if not doc or cite["snapshot_id"] != snapshot.snapshot_id or cite["content_hash"] != doc.content_hash:
                issues.append("snapshot_or_hash_mismatch")
        cited = {c["evidence_id"] for c in result["citations"]}
        if any(not set(claim["evidence_ids"]) <= cited for claim in result["claims"]):
            issues.append("claim_reference_missing")
        if result["metadata"].get("export_redacted"):
            issues.append("redacted_record_not_exact_quote_evidence")
        rows.append({"case": name, "citations": len(result["citations"]),
                     "claims": len(result["claims"]), "passed": not issues, "issues": issues})
    return {"kind": "structural_provenance_audit_not_semantic_proof", "records": rows,
            "passed": all(r["passed"] for r in rows), "citation_count": sum(r["citations"] for r in rows),
            "claim_count": sum(r["claims"] for r in rows)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = audit(args.directory)
    write_json(args.output, report)
    print(json.dumps({"passed": report["passed"], "records": len(report["records"]),
                      "citations": report["citation_count"], "claims": report["claim_count"]}))
    return 0 if report["passed"] and report["records"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
