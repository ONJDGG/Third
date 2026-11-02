# 能力验收与证据

本项目的验收重点是：回答有依据、冲突有处理、资料不足不臆测、工具失败能说明、决策过程可检查、执行额度可控制。这里记录能力与证据，不包含外部业务资料原文。

## 1. 用户需要得到什么

| 用户需求 | 预期行为 | 证据 |
| --- | --- | --- |
| 找到制度答案 | 先检索，再读取原文，给出适用范围明确的回答 | [正常输出](../examples/live-codex/normal.output.json) |
| 核对不同规定 | 比较原文及适用条件；有明确替代条款才能消解，否则展示差异并追问 | [未消解冲突](../examples/live-codex/conflict.output.json)、[明确替代](../examples/live-codex/resolved.output.json) |
| 提问超出资料范围 | 说明当前可访问资料缺什么，不用常识编造企业制度 | [资料不足](../examples/live-codex/outside.output.json) |
| 换一种表达提问 | 识别口语或相近表达，仍找到相关依据 | [改写问题](../examples/live-codex/paraphrase.output.json) |
| 继续上一轮追问 | 结合前文理解省略信息，重新核对本轮资料 | [上下文追问](../examples/live-codex/followup.output.json) |
| 遇到工具故障 | 根据错误选择恢复或停止，区分工具不可用与知识缺失 | [暂时故障](../examples/live-codex/tool-recovery.output.json)、[持续故障](../examples/live-codex/tool-failure.output.json) |
| 制度发生变化 | 新请求使用更新后的资料，答案随依据变化 | [更新后输出](../examples/live-codex/replacement.output.json) |
| 一个问题包含多个事项 | 保留有依据的部分，明确剩余缺口，不伪装全部完成 | [部分可答](../examples/live-codex/partial.output.json) |

完整输入与预期位于 [场景清单](../examples/cases/manifest.json)。每个场景同时保留输入、实际输出和逐步工作记录。

## 2. 两条真实决策路径

同一个期限查询，在不同资料下形成不同路径。下表概括实际Trace；完整参数和简短动作依据仍保留在对应记录中。

### 有充分依据时结束

| 步骤 | 模型选择的动作 | 工具参数或返回摘要 | 后续决定 |
| --- | --- | --- | --- |
| 1 | search | 检索期限、适用范围和替代关系，找到D01 | 检索摘要不能替代原文，继续读取 |
| 2 | read | D01、2026-01-01、clause1；原文规定30天及起算点 | 取得支持结论的原文 |
| 3 | finish | 回答30天、附D01引用，状态answered | 当前问题已获得有据答案 |

参见 [实际输入](../examples/live-codex/normal.input.json)、[输出](../examples/live-codex/normal.output.json)、[Trace](../examples/live-codex/normal.trace.json)。

### 有冲突时继续查证

| 步骤 | 模型选择的动作 | 工具参数或返回摘要 | 后续决定 |
| --- | --- | --- | --- |
| 1 | search | 同主题检索同时找到D01、D02 | 比较两份可能适用的资料 |
| 2 | read | D01、2026-01-01、clause1，规定30天 | 继续核对另一来源 |
| 3 | read | D02、2026-06-01、clause1，规定15天 | 不能仅按版本日期选一个值 |
| 4 | search | 补查适用范围、生效、替代与废止，仍未取得消解依据 | 保留冲突，说明资料缺口 |
| 5 | finish | 列出两种规定及双方引用，状态needs_clarification | 请求确认适用制度 |

参见 [实际输入](../examples/live-codex/conflict.input.json)、[输出](../examples/live-codex/conflict.output.json)、[Trace](../examples/live-codex/conflict.trace.json)。

差异来自模型看到的工具结果：第一条3步结束，第二条多读取一份资料并补充检索，以5步和追问结束。程序提供执行骨架，真实后端负责逐步选择动作；固定重试、Mock和旧决策回放分别记录，不计作新的真实模型决策。

## 3. 工程边界如何检查

| 边界 | 实现方式 | 验证入口 |
| --- | --- | --- |
| 引用可追溯 | 证据ID绑定请求、快照、权限范围、文档版本和片段；原文由程序组装 | [真实引用审计](../examples/engineering/live-provenance-audit.json) |
| 权限不由模型决定 | 检索前过滤，读取再次校验，模型不能更改可信访问范围 | tests/test_protocol_knowledge.py、访问限制场景 |
| 资料不混版本 | 每次请求固定一版知识快照，下次请求才看到更新 | 不可变快照、更新和旧证据测试 |
| 失败有明确语义 | 区分资料不足、追问、工具错误、模型错误和预算耗尽 | src/agent.py、错误场景与工程测试 |
| 执行有上限 | 默认10次决策、8次工具、20次模型请求，另设单次与全局超时 | src/config.py、[真实预算测试](../examples/engineering/live-budget.output.json) |
| 输入输出可检查 | 严格格式、大小和字段校验，终端JSON与诊断分离，输出不覆盖旧证据 | src/protocol.py、src/safeio.py、相关回归 |
| 环境可复现 | 无第三方运行依赖，离线入口、干净环境及跨平台CI | [干净环境](../examples/clean-submission/summary.json)、[CI](https://github.com/ONJDGG/Third/actions/workflows/offline.yml) |

将工具上限设为1次的真实验证中，程序完成1次工具调用和2次模型请求后返回：

```json
{"status": "incomplete", "reason_code": "tool_limit"}
```

这表示执行额度用尽、查证尚未完成，不表示企业没有相关制度。早期误归类及修复记录保留于评估文档。

## 4. 验证层次与当前结果

- 自动检查：50项工程回归、14组离线模拟场景、14组真实模型场景和4次真实重复验证。
- 原文核对：检查引用版本、内容、读取记录及关键结论的证据关联。
- 人工检查：作者已检查测试用例并手动模拟用户问答，提出可操作性与说明方式的优化反馈，见 [人工验证记录](09-manual-validation.md)。
- AI辅助复核：已有JSON复核记录保留其原始来源标记，与作者人工检查分别保存。

这些结果覆盖当前合成场景，不代表大规模线上准确率或独立第三方审计。完整统计、失败案例、模型接入边界和后续工作见 [评估](03-evaluation.md)。
