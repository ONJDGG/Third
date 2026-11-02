"""Validated immutable corpus snapshots and authorization before retrieval."""
from dataclasses import dataclass
import hashlib
import json
import re

from .protocol import ProtocolError, date, fields, string, strings
from .safeio import load_json


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Fragment:
    fragment_id: str
    text: str


@dataclass(frozen=True)
class Document:
    document_id: str
    version_date: str
    title: str
    topic: str
    scope: str
    source: str
    visibility: str
    groups: tuple
    effective_from: str | None
    effective_to: str | None
    supersedes: tuple
    fragments: tuple
    content_hash: str

    def accessible(self, groups):
        return self.visibility == "public" or bool(set(self.groups) & set(groups))

    def metadata(self):
        return {k: getattr(self, k) for k in ("document_id", "version_date", "title", "topic",
                 "scope", "source", "effective_from", "effective_to", "supersedes", "content_hash")}


@dataclass(frozen=True)
class Snapshot:
    documents: tuple
    snapshot_id: str

    @classmethod
    def load(cls, path):
        return cls.from_data(load_json(path, 2097152))

    @classmethod
    def from_data(cls, data):
        fields(data, ("schema_version", "documents"))
        if data["schema_version"] != "1.0":
            raise ProtocolError("corpus_schema_version")
        if not isinstance(data["documents"], list) or not 1 <= len(data["documents"]) <= 1000:
            raise ProtocolError("corpus_size")
        documents, seen = [], {}
        for index, raw in enumerate(data["documents"]):
            try:
                fields(raw, ("document_id", "version_date", "title", "topic", "scope", "source",
                             "visibility", "groups", "effective_from", "effective_to",
                             "supersedes", "fragments"))
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", raw["document_id"]):
                    raise ProtocolError("document_identifier")
                date(raw["version_date"])
                for k in ("title", "topic", "source"):
                    string(raw[k], 300)
                string(raw["scope"], 500, empty=True)
                strings(raw["groups"], 12, 64)
                strings(raw["supersedes"], 12, 80)
                if raw["visibility"] not in ("public", "restricted"):
                    raise ProtocolError("visibility")
                if raw["visibility"] == "restricted" and not raw["groups"]:
                    raise ProtocolError("missing_access_policy")
                for k in ("effective_from", "effective_to"):
                    if raw[k] is not None:
                        date(raw[k])
                if raw["effective_from"] and raw["effective_to"]:
                    if raw["effective_from"] > raw["effective_to"]:
                        raise ProtocolError("effective_range")
                fragments = raw["fragments"]
                if not isinstance(fragments, list) or not 1 <= len(fragments) <= 20:
                    raise ProtocolError("fragment_count")
                ids, parsed = set(), []
                for fragment in fragments:
                    fields(fragment, ("fragment_id", "text"))
                    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", fragment["fragment_id"]):
                        raise ProtocolError("fragment_identifier")
                    if fragment["fragment_id"] in ids:
                        raise ProtocolError("duplicate_fragment")
                    ids.add(fragment["fragment_id"])
                    string(fragment["text"], 2000)
                    parsed.append(Fragment(**fragment))
                content_hash = digest(raw)
                key = (raw["document_id"], raw["version_date"])
                if key in seen:
                    if seen[key] != content_hash:
                        raise ProtocolError("conflicting_document_version")
                    continue
                seen[key] = content_hash
                values = {**raw, "groups": tuple(raw["groups"]),
                          "supersedes": tuple(raw["supersedes"]), "fragments": tuple(parsed),
                          "content_hash": content_hash}
                documents.append(Document(**values))
            except (ProtocolError, TypeError, KeyError) as exc:
                raise ProtocolError(f"corpus_document_{index}_invalid") from exc
        documents.sort(key=lambda d: (d.document_id, d.version_date))
        return cls(tuple(documents), digest([d.content_hash for d in documents]))

    def get(self, document_id, version_date, groups):
        for doc in self.documents:
            if (doc.document_id, doc.version_date) == (document_id, version_date):
                if doc.accessible(groups):
                    return doc
        return None


ALIASES = {"垫付": "报销", "花的钱": "报销", "花销": "报销", "交单": "提交",
           "递单": "提交", "多长时间": "期限", "最迟": "期限", "多少天": "期限",
           "多久": "期限", "打车": "交通费", "出租车": "交通费", "新人": "试用期"}
STOP = ("请问", "一下", "可以", "需要", "应该", "我们", "公司", "员工", "的", "了", "吗", "呢")


def normalize(text):
    text = text.lower()
    for a, b in ALIASES.items():
        text = text.replace(a, b)
    for item in STOP:
        text = text.replace(item, "")
    return "".join(re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", text))


def terms(text):
    text = normalize(text)
    return set(text[i:i+2] for i in range(max(0, len(text) - 1))) or {text}


def retrieve(snapshot, query, groups=(), top_k=4, mode="enhanced"):
    """No hidden docs enter scoring, summaries, related-version hints or counts."""
    visible = [d for d in snapshot.documents if d.accessible(groups)]
    candidates = []
    qterms = terms(query)
    for doc in visible:
        text = doc.title + " " + " ".join(f.text for f in doc.fragments)
        if mode == "baseline":
            score = 1.0 if query.strip() in text else 0.0
        else:
            score = len(qterms & terms(text)) / max(1, len(qterms))
            score += 0.25 * len(qterms & terms(doc.title)) / max(1, len(qterms))
        if score > 0:
            candidates.append((score, doc))
    candidates.sort(key=lambda x: (-x[0], x[1].document_id, x[1].version_date))
    result = []
    for score, doc in candidates[:top_k]:
        best = max(doc.fragments, key=lambda f: len(qterms & terms(f.text)))
        item = doc.metadata()
        item.update(fragment_id=best.fragment_id, summary=best.text[:160],
                    summary_truncated=len(best.text) > 160, score=round(score, 4))
        # Hints do not imply precedence. They only surface competing visible sources.
        item["related_sources"] = [
            {"document_id": other.document_id, "version_date": other.version_date,
             "fragment_id": other.fragments[0].fragment_id}
            for other in visible if other.topic == doc.topic and other != doc][:6]
        result.append(item)
    return result
