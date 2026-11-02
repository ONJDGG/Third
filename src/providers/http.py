"""Documented Chat Completions JSON-Schema subset; not every vendor protocol."""
import json
import datetime as dt
from email.utils import parsedate_to_datetime
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

from ..protocol import DECISION_SCHEMA, ProtocolError, strict_json
from .base import BudgetExceeded, ModelFailure, SYSTEM_PROMPT
from .process import run_process


class HTTPProvider:
    name, is_mock = "api", False

    def __init__(self, model, base, key, allow_local=False, transport=None):
        parsed = urlsplit(base)
        local = parsed.hostname in ("127.0.0.1", "localhost", "::1")
        if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
            raise ModelFailure("invalid_endpoint")
        if parsed.scheme != "https" and not (allow_local and local and parsed.scheme == "http"):
            raise ModelFailure("https_required")
        if not model or not key or any(c in key for c in "\r\n"):
            raise ModelFailure("missing_model_or_key")
        self.model, self.url, self.key = model, base.rstrip("/") + "/chat/completions", key
        self.transport = transport or self._transport
        self.last_usage = None

    def _transport(self, payload, timeout, maximum):
        root = str(Path(__file__).resolve().parents[2])
        code, data = run_process([sys.executable, "-m", "src.providers.http_worker"],
                                 json.dumps(payload).encode(), timeout, maximum * 2, cwd=root)
        if code:
            raise ModelFailure("transport_worker_failed")
        try:
            return strict_json(data.decode("utf-8"))
        except (UnicodeError, ProtocolError) as exc:
            raise ModelFailure("provider_protocol") from exc

    def decide(self, context, budget):
        body = {"model": self.model, "max_completion_tokens": 2048, "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "next_decision", "strict": True, "schema": DECISION_SCHEMA}}}
        self.last_usage = None
        for attempt in range(budget.limits.retries + 1):
            timeout = budget.request()
            result = self.transport({"url": self.url, "key": self.key, "body": body,
                                     "timeout": timeout, "max_bytes": budget.limits.response_bytes},
                                    timeout, budget.limits.response_bytes)
            budget.remaining()
            status = result.get("status")
            retryable = status in (429, 500, 502, 503, 504) or result.get("error") == "transport_error"
            if retryable and attempt < budget.limits.retries:
                try:
                    delay = max(0.1, float(result.get("retry_after") or (0.2 * 2**attempt)))
                except ValueError:
                    try:
                        delay = max(0.1, (parsedate_to_datetime(result["retry_after"])
                                          - dt.datetime.now(dt.timezone.utc)).total_seconds())
                    except (ValueError, TypeError, KeyError):
                        delay = 0.2
                if delay >= budget.remaining():
                    raise BudgetExceeded("retry_deadline")
                # Request budget is checked before waiting as well as before sending.
                if budget.requests >= budget.limits.requests:
                    raise BudgetExceeded("request_limit")
                if delay > 30:
                    raise ModelFailure("retry_wait_exceeds_limit")
                time.sleep(delay)
                continue
            if status != 200:
                code = ("authentication_failed" if status in (401, 403) else
                        "rate_limited" if status == 429 else result.get("error", "http_error"))
                raise ModelFailure(code)
            try:
                response = result["body"]
                message = response["choices"][0]["message"]
                if message.get("tool_calls") or message.get("refusal"):
                    raise ModelFailure("unsupported_response")
                raw_usage = response.get("usage") or {}
                if not isinstance(raw_usage, dict):
                    raise ModelFailure("provider_protocol")
                self.last_usage = {k: v for k, v in raw_usage.items()
                                   if k in ("prompt_tokens", "completion_tokens", "total_tokens")
                                   and type(v) is int and v >= 0} or None
                try:
                    return strict_json(message["content"])
                except ProtocolError:
                    return None  # Runtime offers one bounded protocol repair; raw text stays private.
            except (KeyError, IndexError, TypeError, ProtocolError) as exc:
                raise ModelFailure("provider_protocol") from exc
