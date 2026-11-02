"""Small strict protocol, independent of any model SDK."""
import datetime as dt
import json
import re

PROTOCOL_VERSION = "1.0"
STATUSES = ("answered", "needs_clarification", "insufficient_evidence", "tool_error",
            "model_error", "incomplete")


class ProtocolError(ValueError):
    """Safe machine-readable error; never includes raw model text or paths."""


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProtocolError("duplicate_json_key")
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ProtocolError("nonfinite")))
    except (ValueError, RecursionError) as exc:
        raise ProtocolError("invalid_json") from exc


def fields(obj, required, optional=()):
    if not isinstance(obj, dict) or not set(required) <= obj.keys():
        raise ProtocolError("missing_or_invalid_fields")
    if obj.keys() - set(required) - set(optional):
        raise ProtocolError("unknown_fields")


def string(value, limit, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise ProtocolError("invalid_string")
    return value


def integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ProtocolError("invalid_integer")
    return value


def date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ProtocolError("invalid_date")
    try:
        dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ProtocolError("invalid_date") from exc
    return value


def strings(value, count=12, limit=1000):
    if not isinstance(value, list) or len(value) > count:
        raise ProtocolError("invalid_list")
    for item in value:
        string(item, limit)
    return value


def validate_input(value):
    fields(value, ("question",), ("history", "conditions", "as_of"))
    string(value["question"], 4000)
    history = value.get("history", [])
    if not isinstance(history, list) or len(history) > 12:
        raise ProtocolError("history_limit")
    for turn in history:
        fields(turn, ("role", "content"))
        if turn["role"] not in ("user", "assistant"):
            raise ProtocolError("invalid_history_role")
        string(turn["content"], 4000)
    if sum(len(t["content"]) for t in history) > 16000:
        raise ProtocolError("history_limit")
    conditions = value.get("conditions", {})
    fields(conditions, (), ("department", "region", "employment_status", "expense_type"))
    for item in conditions.values():
        string(item, 200)
    if "as_of" in value:
        date(value["as_of"])
    return strict_json(json.dumps(value, ensure_ascii=False))


def decision(action, reason, **kwargs):
    value = dict(action=action, reason=reason, query="", top_k=4, document_id="",
                 version_date="", fragment_id="", answer="", claims=[], evidence_ids=[],
                 gaps=[], status="", clarification_question="")
    value.update(kwargs)
    return value


_STR = {"type": "string"}
_LIST = {"type": "array", "items": _STR}
_PROPERTIES = {k: _STR for k in ("reason", "query", "document_id", "version_date",
                                "fragment_id", "answer", "clarification_question")}
_PROPERTIES.update(action={"type": "string", "enum": ["search", "read", "finish"]},
                   top_k={"type": "integer"}, evidence_ids=_LIST, gaps=_LIST,
                   status={"type": "string", "enum": ["", *STATUSES]},
                   claims={"type": "array", "items": {"type": "object", "properties": {
                       "text": _STR, "evidence_ids": _LIST},
                       "required": ["text", "evidence_ids"], "additionalProperties": False}})
DECISION_SCHEMA = {"type": "object", "properties": _PROPERTIES,
                   "required": list(_PROPERTIES), "additionalProperties": False}


def validate_decision(value):
    fields(value, _PROPERTIES)
    if value["action"] not in ("search", "read", "finish"):
        raise ProtocolError("unknown_action")
    for name in ("reason", "query", "document_id", "version_date", "fragment_id",
                 "answer", "clarification_question"):
        string(value[name], 6000 if name == "answer" else 1000, empty=True)
    string(value["reason"], 600)
    integer(value["top_k"], 1, 6)
    strings(value["evidence_ids"], 12, 80)
    strings(value["gaps"], 12, 500)
    if value["status"] not in ("", *STATUSES):
        raise ProtocolError("invalid_status")
    if not isinstance(value["claims"], list) or len(value["claims"]) > 12:
        raise ProtocolError("invalid_claims")
    for claim in value["claims"]:
        fields(claim, ("text", "evidence_ids"))
        string(claim["text"], 1500)
        strings(claim["evidence_ids"], 12, 80)
        if not claim["evidence_ids"]:
            raise ProtocolError("claim_without_evidence")
    if value["action"] == "search":
        string(value["query"], 300)
    if value["action"] == "read":
        for name in ("document_id", "fragment_id"):
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value[name]):
                raise ProtocolError("invalid_identifier")
        date(value["version_date"])
    if value["action"] == "finish":
        string(value["answer"], 6000)
        if value["status"] not in STATUSES:
            raise ProtocolError("missing_status")
        if value["status"] == "answered" and not value["claims"]:
            raise ProtocolError("answer_without_claims")
        if value["status"] == "needs_clarification":
            string(value["clarification_question"], 1000)
        if value["status"] in ("needs_clarification", "insufficient_evidence") and not value["gaps"]:
            raise ProtocolError("missing_gap")
    return value
