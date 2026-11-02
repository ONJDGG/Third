"""Optional CLI decision backend, isolated from business files and account data."""
import json
from pathlib import Path
import shutil
import tempfile

from ..protocol import DECISION_SCHEMA, ProtocolError, strict_json
from ..safeio import scratch_directory
from .base import ModelFailure, SYSTEM_PROMPT
from .process import run_process


class CodexProvider:
    name, is_mock = "codex", False

    def __init__(self, model=None, executable="codex"):
        self.executable = shutil.which(executable)
        if not self.executable:
            raise ModelFailure("codex_unavailable")
        self.model = model or "cli-default-not-disclosed"
        self.requested_model = model
        self.last_usage = None

    def decide(self, context, budget):
        timeout = budget.request()
        self.last_usage = None
        with tempfile.TemporaryDirectory(prefix="decision-only-", dir=scratch_directory()) as directory:
            schema = Path(directory) / "decision.schema.json"
            schema.write_text(json.dumps(DECISION_SCHEMA), encoding="utf-8")
            args = [self.executable, "exec", "--ignore-user-config", "--ephemeral",
                    "--sandbox", "read-only", "--skip-git-repo-check", "--json",
                    "--output-schema", str(schema), "-C", directory]
            # Ignore user config to avoid personal MCP servers; also suppress built-in capabilities.
            for setting in ("features.shell_tool=false", "features.apps=false", "features.plugins=false",
                            "features.hooks=false", "features.multi_agent=false", "features.memories=false",
                            "features.browser_use=false", "features.browser_use_external=false",
                            "features.computer_use=false", "features.view_image=false",
                            "features.code_mode=false",
                            "features.js_repl=false", "web_search=\"disabled\"", "mcp_servers={}",
                            "hide_agent_reasoning=true", "model_reasoning_effort=\"low\""):
                args += ["-c", setting]
            if self.requested_model:
                args += ["--model", self.requested_model]
            args += ["-"]
            prompt = SYSTEM_PROMPT + "\n业务上下文(JSON 数据)：\n" + json.dumps(context, ensure_ascii=False)
            code, output = run_process(args, prompt.encode("utf-8"), timeout,
                                       budget.limits.response_bytes, cwd=directory)
        # The raw event stream is consumed privately and never written to project artifacts.
        messages = []
        completed = False
        try:
            for line in output.decode("utf-8").splitlines():
                event = strict_json(line)
                item = event.get("item", {})
                if item.get("type") not in (None, "agent_message", "reasoning", "error"):
                    raise ModelFailure("codex_unexpected_tool_execution")
                # Diagnostic/reconnect errors are not executions. A successful final turn is
                # mandatory; warnings never make a failed process count as a valid decision.
                if event.get("type") == "turn.failed":
                    raise ModelFailure("codex_call_failed")
                if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                    messages.append(item["text"])
                if event.get("type") == "turn.completed":
                    completed = True
                    raw = event.get("usage") or {}
                    if not isinstance(raw, dict):
                        raise ModelFailure("codex_protocol_error")
                    self.last_usage = {k: v for k, v in raw.items()
                                       if k in ("input_tokens", "cached_input_tokens", "output_tokens")
                                       and type(v) is int and v >= 0} or None
            if code or not completed or len(messages) != 1:
                raise ModelFailure("codex_call_failed")
            try:
                return strict_json(messages[0])
            except ProtocolError:
                return None
        except (UnicodeError, ProtocolError, KeyError, TypeError) as exc:
            raise ModelFailure("codex_protocol_error") from exc
