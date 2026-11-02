"""Bounded model/tool/observation loop. No business answers live in this runtime."""
import json
import time
import uuid

from .config import Limits
from .protocol import PROTOCOL_VERSION, ProtocolError, validate_decision, validate_input
from .providers.base import Budget, BudgetExceeded, ModelFailure
from .safeio import public_export


def run_agent(input_data, tools, provider, limits=None, clock=time.monotonic):
    input_data = validate_input(input_data)
    limits = limits or Limits()
    budget = Budget(limits, clock)
    trace, usage = [], []
    steps = tool_calls = invalid = 0
    status, reason_code, answer = "incomplete", "decision_limit", "任务未完成。"
    citations, claims, gaps, question = [], [], [], ""
    repeated = {}
    try:
        for _ in range(limits.decisions):
            budget.remaining()
            steps += 1
            context = {"input": input_data, "observations": trace,
                       "budget": {"decisions_left": limits.decisions - steps,
                                  "tools_left": limits.tools - tool_calls,
                                  "requests_left": limits.requests - budget.requests},
                       "protocol_version": PROTOCOL_VERSION}
            if len(json.dumps(context, ensure_ascii=False)) > limits.context_chars:
                raise BudgetExceeded("context_limit")
            started = clock()
            raw = provider.decide(context, budget)
            budget.remaining()
            if getattr(provider, "last_usage", None):
                usage.append(dict(provider.last_usage))
            try:
                action = validate_decision(raw)
                if action["action"] == "finish":
                    if action["status"] == "insufficient_evidence" and tool_calls >= limits.tools:
                        raise BudgetExceeded("tool_limit")
                    observed_search = any(t.get("type") == "tool_result"
                                          and t["decision"]["action"] == "search"
                                          and t["result"].get("ok") for t in trace)
                    observed_failure = any(t.get("type") == "tool_result"
                                           and not t["result"].get("ok") for t in trace)
                    if action["status"] == "insufficient_evidence" and not observed_search:
                        raise ValueError("insufficient_without_search")
                    if action["status"] == "tool_error" and not observed_failure:
                        raise ValueError("tool_error_without_observation")
                    resolved = tools.citations(action)
                    if action["status"] == "answered" and not resolved:
                        raise ValueError("answer_without_evidence")
                    citations, claims, gaps = resolved, action["claims"], action["gaps"]
                    answer, status, question = action["answer"], action["status"], action["clarification_question"]
                    reason_code = "completed" if status == "answered" else status
                    trace.append({"type": "decision", "step": steps, "decision": action,
                                  "elapsed_ms": round((clock()-started)*1000, 3)})
                    break
            except (ProtocolError, ValueError, TypeError, KeyError):
                invalid += 1
                trace.append({"type": "validation_error", "step": steps,
                              "error": "invalid_decision_or_evidence",
                              "instruction": "仅使用协议允许动作及本次实际读取的 evidence_id，请修正。"})
                if invalid > 1:
                    status, reason_code, answer = "model_error", "protocol_error", "模型持续返回无效动作或引用。"
                    break
                continue
            if tool_calls >= limits.tools:
                raise BudgetExceeded("tool_limit")
            tool_calls += 1
            result = tools.execute(action, budget.deadline)
            budget.remaining()
            trace.append({"type": "tool_result", "step": steps, "decision": action,
                          "result": result, "elapsed_ms": round((clock()-started)*1000, 3)})
            fingerprint = json.dumps([action["action"], action["query"], action["document_id"],
                                      action["fragment_id"], result], sort_keys=True, ensure_ascii=False)
            repeated[fingerprint] = repeated.get(fingerprint, 0) + 1
            if repeated[fingerprint] == 2:
                trace.append({"type": "runtime_notice", "instruction": "相同动作与观察重复，请改变检索方式或结束。"})
            if repeated[fingerprint] >= 3:
                raise BudgetExceeded("stalled")
    except BudgetExceeded as exc:
        status, reason_code, answer = "incomplete", exc.code, "执行预算耗尽或任务中止，未完成全部查证。"
    except ModelFailure as exc:
        status, reason_code, answer = "model_error", exc.code, "模型调用失败，未生成可靠回答。"
    except KeyboardInterrupt:
        status, reason_code, answer = "incomplete", "cancelled", "任务已取消。"
    if status != "answered" and not gaps:
        gaps = ["本次任务未获得完整且可验证的结论"]
    if not citations and tools.evidence:
        try:
            citations = tools.citations({"evidence_ids": list(tools.evidence), "claims": []})
        except (ValueError, TypeError, KeyError):
            citations = []
    output = {"schema_version": PROTOCOL_VERSION, "answer": answer,
        "claims": claims, "citations": citations, "gaps": gaps, "status": status,
        "reason_code": reason_code, "clarification_question": question, "trace": trace,
        "metadata": {"run_id": uuid.uuid4().hex, "backend": provider.name,
            "is_mock": provider.is_mock, "model": provider.model,
            "snapshot_id": tools.snapshot.snapshot_id, "protocol_version": PROTOCOL_VERSION,
            "prompt_version": "1.0", "retrieval_version": tools.mode + "-1",
            "fault_injection": bool(tools.faults), "decision_steps": steps,
            "tool_calls": tool_calls, "model_requests": budget.requests, "usage": usage or None,
            "elapsed_ms": round((clock()-budget.started)*1000, 3)}}
    exported = public_export(output)
    exported["metadata"]["export_redacted"] = (
        json.dumps(exported, sort_keys=True, ensure_ascii=False)
        != json.dumps(output, sort_keys=True, ensure_ascii=False))
    return exported
