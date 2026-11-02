"""Deterministic observation-driven simulation. Not evidence of LLM decision quality."""
import re

from ..knowledge import normalize
from ..protocol import decision


class MockProvider:
    name = "mock"
    model = "deterministic-observation-policy-v1"
    is_mock = True

    def decide(self, context, budget):
        budget.request()
        events = context["observations"]
        tools = [e for e in events if e["type"] == "tool_result"]
        if tools and not tools[-1]["result"]["ok"]:
            failure = tools[-1]
            failures = [t for t in tools if not t["result"]["ok"]]
            if len(failures) >= 2 or not failure["result"].get("retryable"):
                return decision("finish", "工具持续不可用，停止无依据回答", answer="资料工具不可用，暂时无法完成查证。",
                                status="tool_error", gaps=["无法读取制度依据"])
            return {**failure["decision"], "reason": "观察到暂时工具错误，在预算内重试"}
        searches = [t for t in tools if t["decision"]["action"] == "search" and t["result"]["ok"]]
        if not searches:
            question = context["input"]["question"]
            history = context["input"].get("history", [])
            if history:
                question = " ".join(t["content"] for t in history if t["role"] == "user") + " " + question
            return decision("search", "先定位与问题相关的制度", query=question[:300])
        candidates = searches[-1]["result"]["results"]
        target = next((term for term in ("额度", "补贴", "交通费")
                       if term in normalize(context["input"]["question"])), None)
        if target and candidates and not any(target in item["summary"] for item in candidates):
            partial = "期限" in context["input"]["question"] and "期限" in candidates[0]["summary"]
            if partial:
                read_evidence = [t["result"]["evidence"] for t in tools if t["result"].get("evidence")]
                if not read_evidence:
                    item = candidates[0]
                    return decision("read", "先核对可回答部分", **{k: item[k] for k in
                                    ("document_id", "version_date", "fragment_id")})
                evidence = read_evidence[0]
                return decision("finish", "仅部分问题有依据，明确缺口", status="insufficient_evidence",
                                answer=evidence["quote"] + "其他所问事项在当前资料中缺少依据。",
                                claims=[{"text": evidence["quote"], "evidence_ids": [evidence["evidence_id"]]}],
                                gaps=["缺少" + target + "资料"])
            if len(searches) < 2:
                return decision("search", "候选未覆盖所问事项，缩小检索主题", query=target)
            candidates = []
        if not candidates:
            if len(searches) < 2:
                return decision("search", "初次未找到依据，改写检索表达", query=normalize(context["input"]["question"])[:300] or "资料")
            return decision("finish", "补查后仍未获得依据", answer="当前可访问资料未找到支持该问题的制度依据。",
                            status="insufficient_evidence", gaps=["缺少相关制度资料"])
        read = [t["result"]["evidence"] for t in tools
                if t["decision"]["action"] == "read" and t["result"].get("evidence")]
        keys = {(e["document_id"], e["version_date"], e["fragment_id"]) for e in read}
        pending = []
        for item in candidates:
            pending.append(item)
            pending.extend(item.get("related_sources", []))
        for item in pending:
            key = (item["document_id"], item["version_date"], item["fragment_id"])
            if key not in keys:
                return decision("read", "读取候选或相关制度，检查原文与竞争依据",
                                **{k: item[k] for k in ("document_id", "version_date", "fragment_id")})
        conditions = " ".join(context["input"].get("conditions", {}).values())
        question = context["input"]["question"] + " " + conditions
        # Explicit fixture source markers are a simulation rule, NOT a real injection detector.
        relevant = [e for e in read if e["topic"] == candidates[0]["topic"]
                    and e["source"] != "synthetic-adversarial"]
        as_of = context["input"].get("as_of")
        if as_of:
            relevant = [e for e in relevant if (not e["effective_from"] or e["effective_from"] <= as_of)
                        and (not e["effective_to"] or e["effective_to"] >= as_of)]
        original = list(relevant)
        superseded = {doc for e in relevant for doc in e["supersedes"]}
        relevant = [e for e in relevant if e["document_id"] not in superseded]
        if "试用期" in question:
            scoped = [e for e in relevant if "试用期" in e["scope"]]
            relevant = scoped or relevant
        if not relevant:
            return decision("finish", "没有适用时段的依据", answer="当前资料无法确定该时段的适用制度。",
                            status="insufficient_evidence", gaps=["缺少指定时段的适用依据"])
        days = {tuple(re.findall(r"\d+\s*天", e["quote"])) for e in relevant}
        ids = [e["evidence_id"] for e in original]
        if len(days) > 1:
            claims = [{"text": f'{e["document_id"]}：{e["quote"]}', "evidence_ids": [e["evidence_id"]]} for e in relevant]
            if len(searches) < 2:
                return decision("search", "发现不同规定，补查适用范围与优先级", query="报销期限 适用范围 优先级 替代", top_k=6)
            return decision("finish", "补查后仍无消解依据，请确认制度", status="needs_clarification",
                            answer="现有资料存在冲突：" + "；".join(c["text"] for c in claims),
                            claims=claims, evidence_ids=ids, gaps=["缺少适用范围或优先级依据"],
                            clarification_question="请确认适用哪个制度，或补充部门、地区和制度优先级依据。")
        selected = relevant[0]
        return decision("finish", "已读取适用原文，按证据回答", status="answered",
                        answer=selected["quote"], evidence_ids=ids,
                        claims=[{"text": selected["quote"], "evidence_ids": [selected["evidence_id"]]}])
