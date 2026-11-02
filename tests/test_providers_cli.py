import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from src.config import Limits
from src.main import ROOT
from src.protocol import decision
from src.providers.base import Budget, BudgetExceeded, ModelFailure
from src.providers.codex import CodexProvider
from src.providers.http import HTTPProvider
from src.providers.process import clean_environment, run_process
from src.safeio import load_json, public_export, scratch_directory


def envelope(value=None):
    return {"status": 200, "body": {"choices": [{"message": {"content": json.dumps(
        value or decision("search", "查资料", query="报销"))}}],
        "usage": {"total_tokens": 42, "private_field": "must-not-export"}}}


class HTTPTests(unittest.TestCase):
    def provider(self, transport):
        return HTTPProvider("test", "https://provider.example/v1", "test-key", transport=transport)

    def test_explicit_endpoint_boundary(self):
        for base in ("http://remote.example/v1", "https://user:pass@127.0.0.1", "https://remote.example/?secret=x"):
            with self.subTest(base=base), self.assertRaises(ModelFailure):
                HTTPProvider("model", base, "key")

    def test_usage_allowlist_and_schema(self):
        seen = []
        provider = self.provider(lambda payload, *_: seen.append(payload) or envelope())
        action = provider.decide({"input": {"question": "q"}}, Budget(Limits()))
        self.assertEqual(action["action"], "search")
        self.assertEqual(provider.last_usage, {"total_tokens": 42})
        self.assertEqual(seen[0]["body"]["response_format"]["type"], "json_schema")

    def test_authentication_never_retried(self):
        calls = []
        provider = self.provider(lambda *_: calls.append(1) or {"status": 401})
        with self.assertRaises(ModelFailure) as caught:
            provider.decide({}, Budget(Limits()))
        self.assertEqual(caught.exception.code, "authentication_failed")
        self.assertEqual(len(calls), 1)

    def test_rate_limit_retry_consumes_requests(self):
        responses = iter([{"status": 429, "retry_after": "0.01"}, envelope()])
        provider = self.provider(lambda *_: next(responses))
        budget = Budget(Limits())
        provider.decide({}, budget)
        self.assertEqual(budget.requests, 2)

    def test_retry_cannot_bypass_deadline_or_request_budget(self):
        for limits, response, code in (
            (Limits(requests=1), {"status": 503}, "request_limit"),
            (Limits(task_seconds=0.1), {"status": 429, "retry_after": "500"}, "retry_deadline")):
            with self.subTest(code=code), self.assertRaises(BudgetExceeded) as caught:
                self.provider(lambda *_: response).decide({}, Budget(limits))
            self.assertEqual(caught.exception.code, code)

    def test_invalid_provider_response_is_explicit(self):
        with self.assertRaises(ModelFailure):
            self.provider(lambda *_: {"status": 200, "body": {"choices": []}}).decide({}, Budget(Limits()))

    def test_long_retry_after_does_not_send_early(self):
        calls = []
        provider = self.provider(lambda *_: calls.append(1) or {"status": 429, "retry_after": "60"})
        with self.assertRaises(ModelFailure) as caught:
            provider.decide({}, Budget(Limits()))
        self.assertEqual(caught.exception.code, "retry_wait_exceeds_limit")
        self.assertEqual(len(calls), 1)

    def test_real_http_worker_and_cross_origin_redirect_block(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            redirects = False
            def log_message(self, *_):
                pass
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                if self.redirects:
                    self.send_response(302)
                    self.send_header("Location", "http://127.0.0.1:1/private")
                    self.end_headers()
                else:
                    payload = json.dumps(envelope()["body"]).encode()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            provider = HTTPProvider("test", f"http://127.0.0.1:{server.server_port}/v1", "synthetic-key", allow_local=True)
            self.assertEqual(provider.decide({}, Budget(Limits()))["action"], "search")
            Handler.redirects = True
            with self.assertRaises(ModelFailure):
                provider.decide({}, Budget(Limits()))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class ProcessTests(unittest.TestCase):
    def test_timeout_reaps_owned_process(self):
        start = time.monotonic()
        with self.assertRaises(BudgetExceeded):
            run_process([sys.executable, "-c", "import time; time.sleep(60)"], b"", 0.2, 10000)
        self.assertLess(time.monotonic() - start, 7)

    def test_process_response_size_limit(self):
        with self.assertRaises(ModelFailure):
            run_process([sys.executable, "-c", "print('x'*50000)"], b"", 5, 1024)

    def test_sensitive_environment_not_inherited(self):
        with patch.dict(os.environ, {"AGENT_API_KEY": "sensitive", "OTHER_SECRET": "secret"}):
            env = clean_environment()
        self.assertNotIn("AGENT_API_KEY", env)
        self.assertNotIn("OTHER_SECRET", env)

    def test_cancellation_terminates_owned_process(self):
        import src.providers.process as module
        actual = module.terminate_owned
        killed = []
        def tracked(process):
            actual(process)
            killed.append(process.poll())
        with patch.object(module, "pause", side_effect=KeyboardInterrupt), patch.object(module, "terminate_owned", tracked):
            with self.assertRaises(KeyboardInterrupt):
                run_process([sys.executable, "-c", "import time; time.sleep(60)"], b"", 5, 10000)
        self.assertTrue(killed)
        self.assertIsNotNone(killed[0])

    def test_codex_unexpected_execution_rejected(self):
        stream = json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": "x"}}).encode()
        with patch("src.providers.codex.shutil.which", return_value="codex"), patch("src.providers.codex.run_process", return_value=(0, stream)):
            with self.assertRaises(ModelFailure) as caught:
                CodexProvider().decide({}, Budget(Limits()))
        self.assertEqual(caught.exception.code, "codex_unexpected_tool_execution")

    def test_codex_capability_controls_and_no_raw_export(self):
        action = decision("search", "查证", query="q")
        stream = "\n".join([json.dumps({"type": "thread.started", "thread_id": "PRIVATE_SESSION"}),
                              json.dumps({"type": "item.completed", "item": {"type": "error", "message": "nonfatal diagnostic"}}),
                              json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(action)}}),
                              json.dumps({"type": "turn.completed", "usage": {"input_tokens": 50}})])
        with patch("src.providers.codex.shutil.which", return_value="codex"), patch("src.providers.codex.run_process", return_value=(0, stream.encode())) as runner:
            result = CodexProvider().decide({}, Budget(Limits()))
        args = runner.call_args.args[0]
        self.assertIn("--ignore-user-config", args)
        self.assertIn("features.shell_tool=false", args)
        self.assertNotIn("PRIVATE_SESSION", str(result))

    def test_codex_warning_alone_is_not_a_success(self):
        stream = json.dumps({"type": "item.completed", "item": {"type": "error", "message": "diagnostic"}})
        with patch("src.providers.codex.shutil.which", return_value="codex"), patch("src.providers.codex.run_process", return_value=(0, stream.encode())):
            with self.assertRaises(ModelFailure):
                CodexProvider().decide({}, Budget(Limits()))


class CLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "src.main", *args], cwd=ROOT,
                              capture_output=True, encoding="utf-8", timeout=15)

    def test_utf8_stdout_is_single_json(self):
        process = self.run_cli("--input", "examples/cases/normal.input.json")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "answered")

    def test_write_failure_does_not_report_success(self):
        with tempfile.TemporaryDirectory(dir=scratch_directory()) as directory:
            out = Path(directory)/"中文.json"
            out.write_text("original", encoding="utf-8")
            process = self.run_cli("--input", "examples/cases/normal.input.json", "--output", str(out))
            self.assertEqual(process.returncode, 4)
            self.assertEqual(json.loads(process.stdout)["status"], "io_error")
            self.assertEqual(out.read_text(encoding="utf-8"), "original")

    def test_bad_input_and_anonymous_doctor(self):
        process = self.run_cli("--doctor")
        self.assertEqual(json.loads(process.stdout)["authentication"], "not_inspected")
        process = self.run_cli()
        self.assertEqual(process.returncode, 2)
        self.assertNotIn(str(ROOT), process.stdout + process.stderr)

    def test_export_masks_private_markers(self):
        value = public_export({"answer": "Bearer topsecret user@example.com C:\\Users\\person\\auth.json sk-abcdefghijk"})
        self.assertNotIn("topsecret", value["answer"])
        self.assertNotIn("user@example.com", value["answer"])
        self.assertNotIn("person", value["answer"])
