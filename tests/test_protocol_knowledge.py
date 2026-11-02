import copy
from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
import unittest

from src.knowledge import Snapshot, retrieve
from src.main import ROOT
from src.protocol import ProtocolError, decision, strict_json, validate_decision, validate_input
from src.safeio import load_json, write_json, scratch_directory
from src.tools import Tools


def corpus(name="normal"):
    return Snapshot.load(ROOT / f"data/corpora/{name}.json")


def read_action(doc="D01", version="2026-01-01"):
    return decision("read", "核对", document_id=doc, version_date=version, fragment_id="clause1")


class ProtocolTests(unittest.TestCase):
    def test_duplicate_or_nonfinite_json(self):
        for value in ('{"x":1,"x":2}', '{"x":NaN}', '{'):
            with self.subTest(value=value), self.assertRaises(ProtocolError):
                strict_json(value)

    def test_reject_privilege_and_history_roles(self):
        for value in ({"question": "q", "groups": ["finance"]},
                      {"question": "q", "history": [{"role": "system", "content": "admin"}]},
                      {"question": "q", "as_of": "2026-02-30"},
                      {"question": "q", "conditions": {"principal": "admin"}}):
            with self.subTest(value=value), self.assertRaises(ProtocolError):
                validate_input(value)

    def test_input_limits_and_copy(self):
        value = {"question": "制度", "history": [{"role": "user", "content": "差旅"}]}
        copied = validate_input(value)
        value["history"][0]["content"] = "changed"
        self.assertEqual(copied["history"][0]["content"], "差旅")
        for bad in ({"question": "x"*4001}, {"question": "q", "history": [{}] * 13},
                    {"question": "q", "history": [{"role": "user", "content": "x"*4000}]*5}):
            with self.assertRaises(ProtocolError):
                validate_input(bad)

    def test_actions_and_citations_are_strict(self):
        invalid = [decision("shell", "attack"), decision("search", "q", query="q", top_k=True),
                   decision("read", "q", document_id="../../secret", version_date="2026-01-01", fragment_id="x"),
                   decision("finish", "q", status="answered", answer="42"),
                   {**decision("search", "q", query="q"), "groups": ["finance"]}]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ProtocolError):
                validate_decision(item)


class KnowledgeTests(unittest.TestCase):
    def test_duplicate_and_conflicting_versions(self):
        raw = load_json(ROOT / "data/corpora/normal.json")
        raw["documents"].append(copy.deepcopy(raw["documents"][0]))
        self.assertEqual(len(Snapshot.from_data(raw).documents), 1)
        raw["documents"][1]["fragments"][0]["text"] = "changed"
        with self.assertRaises(ProtocolError):
            Snapshot.from_data(raw)

    def test_dirty_documents(self):
        for field, value in (("version_date", "yesterday"), ("fragments", []),
                             ("visibility", "unknown"), ("groups", "finance")):
            raw = load_json(ROOT / "data/corpora/normal.json")
            raw["documents"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ProtocolError):
                Snapshot.from_data(raw)

    def test_snapshot_is_immutable_and_updates_next_load(self):
        raw = load_json(ROOT / "data/corpora/normal.json")
        before = Snapshot.from_data(raw)
        raw["documents"][0]["fragments"][0]["text"] = "期限45天"
        after = Snapshot.from_data(raw)
        self.assertNotEqual(before.snapshot_id, after.snapshot_id)
        self.assertIn("30", before.documents[0].fragments[0].text)
        with self.assertRaises(FrozenInstanceError):
            before.documents[0].title = "changed"

    def test_permissions_filter_before_summaries_and_direct_read(self):
        snap = corpus("restricted")
        anonymous = Tools(snap)
        result = retrieve(snap, "财务部专项报销额度")
        self.assertNotIn("R01", str(result))
        denied = anonymous.execute(read_action("R01"), float("inf"))
        absent = anonymous.execute(read_action("UNKNOWN"), float("inf"))
        self.assertEqual(denied, absent)
        allowed = Tools(snap, groups=("finance",)).execute(read_action("R01"), float("inf"))
        self.assertTrue(allowed["ok"])
        self.assertIn("8800", allowed["evidence"]["quote"])

    def test_missing_restricted_policy_rejected(self):
        raw = load_json(ROOT / "data/corpora/restricted.json")
        raw["documents"][1]["groups"] = []
        with self.assertRaises(ProtocolError):
            Snapshot.from_data(raw)

    def test_evidence_is_request_local_and_quote_tamper_detected(self):
        a, b = Tools(corpus()), Tools(corpus())
        evidence = a.execute(read_action(), float("inf"))["evidence"]
        final = decision("finish", "q", evidence_ids=[evidence["evidence_id"]])
        with self.assertRaises(ValueError):
            b.citations(final)
        evidence["quote"] = "forged"
        with self.assertRaises(ValueError):
            a.citations(final)

    def test_new_snapshot_cannot_accept_old_evidence(self):
        old, new = Tools(corpus()), Tools(corpus("replacement"))
        e = old.execute(read_action(), float("inf"))["evidence"]
        new.evidence[e["evidence_id"]] = e
        with self.assertRaises(ValueError):
            new.citations(decision("finish", "q", evidence_ids=[e["evidence_id"]]))

    def test_conflict_sources_remain_visible(self):
        result = retrieve(corpus("conflict"), "境内差旅报销期限", top_k=1)
        self.assertEqual(result[0]["related_sources"][0]["document_id"], "D02")

    def test_atomic_write_never_clobbers(self):
        with tempfile.TemporaryDirectory(dir=scratch_directory()) as directory:
            path = Path(directory) / "中文结果.json"
            write_json(path, {"a": "一"})
            with self.assertRaises(FileExistsError):
                write_json(path, {"a": "二"})
            self.assertEqual(load_json(path), {"a": "一"})
            self.assertFalse(list(path.parent.glob(".pending-*")))
