"""CLI entry: UTF-8 JSON stdout, safe diagnostics and explicit backend selection."""
import argparse
import json
import os
from pathlib import Path
import sys

from .agent import run_agent
from .config import Limits
from .knowledge import Snapshot
from .protocol import ProtocolError, validate_input
from .providers.base import ModelFailure
from .safeio import load_json, public_export, write_json
from .tools import Tools

ROOT = Path(__file__).resolve().parents[1]


def create_provider(backend, model=None, base=None, allow_local=False):
    if backend == "mock":
        from .providers.mock import MockProvider
        return MockProvider()
    if backend == "codex":
        from .providers.codex import CodexProvider
        return CodexProvider(model, os.environ.get("AGENT_CODEX_BIN", "codex"))
    from .providers.http import HTTPProvider
    return HTTPProvider(model or os.environ.get("AGENT_MODEL"),
                        base or os.environ.get("AGENT_API_BASE", "https://api.openai.com/v1"),
                        os.environ.get("AGENT_API_KEY"), allow_local)


def parser():
    p = argparse.ArgumentParser(description="Evidence-grounded enterprise knowledge agent")
    p.add_argument("--backend", choices=("mock", "api", "codex"), default=os.environ.get("AGENT_BACKEND", "mock"))
    p.add_argument("--input", type=Path)
    p.add_argument("--corpus", type=Path, default=ROOT / "data/corpora/normal.json")
    p.add_argument("--model", default=None)
    p.add_argument("--api-base", default=None)
    p.add_argument("--allow-local-http", action="store_true")
    p.add_argument("--groups", default="", help="Trusted local operator scope; NOT authentication")
    p.add_argument("--output", type=Path)
    p.add_argument("--timeout", type=float, default=300)
    p.add_argument("--call-timeout", type=float, default=90)
    p.add_argument("--max-steps", type=int, default=10)
    p.add_argument("--max-tools", type=int, default=8)
    p.add_argument("--max-requests", type=int, default=20)
    p.add_argument("--fault", choices=("search:once", "search:always", "read:once", "read:always"))
    p.add_argument("--doctor", action="store_true")
    return p


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        if args.backend not in ("mock", "api", "codex"):
            raise ProtocolError("invalid_backend")
        limits = Limits(decisions=args.max_steps, tools=args.max_tools, requests=args.max_requests,
                        task_seconds=args.timeout, call_seconds=args.call_timeout)
        provider = create_provider(args.backend, args.model, args.api_base, args.allow_local_http)
        snapshot = Snapshot.load(args.corpus)
        if args.doctor:
            result = {"status": "configuration_valid", "backend": args.backend,
                      "is_mock": provider.is_mock, "corpus_loaded": True,
                      "connectivity": "not_tested", "authentication": "not_inspected"}
        else:
            if args.input is None:
                raise ProtocolError("input_required")
            input_data = validate_input(load_json(args.input, 65536))
            faults = {}
            if args.fault:
                kind, duration = args.fault.split(":")
                faults[kind] = 1 if duration == "once" else -1
            tools = Tools(snapshot, groups=tuple(filter(None, args.groups.split(","))), faults=faults)
            result = run_agent(input_data, tools, provider, limits)
        if args.output:
            write_json(args.output, result)
        print(json.dumps(public_export(result), ensure_ascii=False, allow_nan=False))
        return 0  # Business statuses live in JSON; evaluator enforces acceptance separately.
    except ProtocolError as exc:
        result, code = {"status": "input_error", "reason_code": str(exc)}, 2
    except ModelFailure as exc:
        result, code = {"status": "configuration_error", "reason_code": exc.code}, 3
    except (OSError, ValueError):
        result, code = {"status": "io_error", "reason_code": "load_or_write_failed"}, 4
    print(json.dumps(result, ensure_ascii=False))
    print(result["reason_code"], file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
