"""Read-only business tools, host-bound authorization, request-local evidence."""
import time
import uuid

from .knowledge import digest, retrieve
from .protocol import ProtocolError, validate_decision


class Tools:
    def __init__(self, snapshot, groups=(), faults=None, mode="enhanced", clock=time.monotonic):
        self.snapshot = snapshot
        self.groups = tuple(groups)
        self.faults = dict(faults or {})
        if any(k not in ("search", "read") or type(v) is not int or v < -1
               for k, v in self.faults.items()):
            raise ValueError("invalid_fault_configuration")
        self.mode = mode
        self.clock = clock
        self.evidence = {}
        self.request_nonce = uuid.uuid4().hex
        self.scope_hash = digest(sorted(self.groups))

    def execute(self, action, deadline):
        try:
            validate_decision(action)
            if action["action"] not in ("search", "read"):
                raise ProtocolError("not_a_tool")
        except (ProtocolError, TypeError, KeyError):
            return {"ok": False, "error": "invalid_tool_arguments", "retryable": False}
        if self.clock() >= deadline:
            return {"ok": False, "error": "deadline", "retryable": False}
        kind = action["action"]
        if self.faults.get(kind, 0):
            if self.faults[kind] > 0:
                self.faults[kind] -= 1
            return {"ok": False, "error": "tool_unavailable", "retryable": True,
                    "fault_injected": True}
        if kind == "search":
            return {"ok": True, "results": retrieve(self.snapshot, action["query"], self.groups,
                                                    action["top_k"], self.mode)}
        doc = self.snapshot.get(action["document_id"], action["version_date"], self.groups)
        fragment = next((f for f in doc.fragments if f.fragment_id == action["fragment_id"]), None) if doc else None
        if fragment is None:
            return {"ok": False, "error": "not_found_or_denied", "retryable": False}
        eid = "E-" + digest([self.request_nonce, self.snapshot.snapshot_id, self.scope_hash, doc.content_hash,
                             fragment.fragment_id])[:24]
        item = {**doc.metadata(), "fragment_id": fragment.fragment_id, "quote": fragment.text,
                "evidence_id": eid, "snapshot_id": self.snapshot.snapshot_id,
                "adjacent_fragments": [f.fragment_id for f in doc.fragments]}
        self.evidence[eid] = item
        return {"ok": True, "evidence": item}

    def citations(self, decision):
        used = list(dict.fromkeys(decision["evidence_ids"] + [
            eid for claim in decision["claims"] for eid in claim["evidence_ids"]]))
        result = []
        for eid in used:
            evidence = self.evidence.get(eid)
            if not evidence or evidence["snapshot_id"] != self.snapshot.snapshot_id:
                raise ValueError("unread_or_foreign_evidence")
            doc = self.snapshot.get(evidence["document_id"], evidence["version_date"], self.groups)
            if not doc or evidence["content_hash"] != doc.content_hash:
                raise ValueError("evidence_access_or_version")
            fragment = next((f for f in doc.fragments if f.fragment_id == evidence["fragment_id"]), None)
            if not fragment or evidence["quote"] != fragment.text:
                raise ValueError("evidence_quote_changed")
            result.append({**doc.metadata(), "evidence_id": eid,
                           "fragment_id": fragment.fragment_id, "quote": fragment.text,
                           "snapshot_id": self.snapshot.snapshot_id,
                           "adjacent_fragments": [f.fragment_id for f in doc.fragments]})
        return result
