# 评估与已知限制

## 当前结论

发布前离线回归50项通过；14组Mock场景通过；全新无pip虚拟环境中14组离线场景通过。完整真实Codex验收14/14通过，冲突与资料外问题各额外重复2次也通过。真实工具调用上限验证明确返回incomplete/tool_limit。

我已人工检查测试用例，并手动模拟用户问答、提出使用体验与说明方式的优化建议，见 [人工检查记录](09-manual-validation.md)。已有自动断言、原文审计与AI复核记录继续分别保留，当前验证结果覆盖所用合成样本，不代表线上整体准确率或第三方审计。

## 可直接复核的实际材料

| 材料 | 入口 | 边界 |
| --- | --- | --- |
| 发布前工程测试 | [verification-cross-platform-fix/tests.json](../examples/engineering/verification-cross-platform-fix/tests.json) | Windows、Python3.14.0，50 tests，退出0 |
| 远端平台矩阵 | [GitHub Actions](https://github.com/ONJDGG/Third/actions/workflows/offline.yml) | Windows/Linux × Python3.11/3.14；核对最终提交的运行结果 |
| 最终离线业务评估 | [mock-final/summary.json](../examples/mock-final/summary.json) | 14/14，确定性模拟决策 |
| 已保存原文溯源审计 | [mock-provenance-audit.json](../examples/engineering/mock-provenance-audit.json) | 14条记录、14处引用、12条claims，无结构错误；不是语义证明 |
| AI逐项语义复核 | [mock-semantic-review.json](../examples/engineering/mock-semantic-review.json) | 明确标记AI复核，非独立人工审核 |
| 作者人工检查 | [人工用例检查与手动问答](09-manual-validation.md) | 已完成，记录使用反馈与已落实调整；无逐条手工终端日志或人工通过率 |
| 干净虚拟环境 | [环境说明](../examples/engineering/clean-environment.json)、[最终源码复现](../examples/clean-submission/summary.json) | --without-pip，无第三方依赖，14/14 |
| 检索基线 | [retrieval-benchmark.json](../examples/engineering/verification-release/retrieval-benchmark.json) | 固定小型合成集，非线上业务分布 |
| 真实正常路径 | [proxy-smoke/normal.output.json](../examples/live-codex-proxy-smoke/normal.output.json) | 3次真实决策，search→read→finish，约65秒 |
| 完整真实验收 | [live-codex/summary.json](../examples/live-codex/summary.json) | 14/14、49次真实模型请求，每场景约58—105秒 |
| 真实重复验证 | [repeat/summary.json](../examples/live-codex-repeat/summary.json) | 冲突、资料外各2次，4/4；正常路径另有两次成功记录 |
| 真实证据审计与复核 | [溯源](../examples/engineering/live-provenance-audit.json)、[AI复核](../examples/engineering/live-semantic-review.json) | 14份记录、14处引用、14条claims，结构无误；非独立人工审核 |
| 新运行时兼容回放 | [live-decision-replay-release.json](../examples/engineering/live-decision-replay-release.json) | 重放原决策验证后续状态校验兼容性，不是新的真实模型运行 |
| 真实执行上限 | [live-budget.output.json](../examples/engineering/live-budget.output.json) | 允许1次业务工具调用，真实2次模型决策后返回incomplete/tool_limit |

输入与独立预期位于 [manifest](../examples/cases/manifest.json)，各目录中同名 `.input.json`、`.output.json`、`.trace.json` 保存实际材料；评估文档下表按场景导航。

| 场景 | 预期 | Mock输出 | 真实输出 |
| --- | --- | --- | --- |
| 明确答案 | 30天，D01 | [normal](../examples/mock-final/normal.output.json) | [normal](../examples/live-codex/normal.output.json) |
| 无优先级冲突 | 查证后追问，双方证据 | [conflict](../examples/mock-final/conflict.output.json) | [conflict](../examples/live-codex/conflict.output.json) |
| 明确替代 | 15天，消解冲突 | [resolved](../examples/mock-final/resolved.output.json) | [resolved](../examples/live-codex/resolved.output.json) |
| 资料外 | 不编造补贴 | [outside](../examples/mock-final/outside.output.json) | [outside](../examples/live-codex/outside.output.json) |
| 相似改写 | 仍找到30天依据 | [paraphrase](../examples/mock-final/paraphrase.output.json) | [paraphrase](../examples/live-codex/paraphrase.output.json) |
| 上下文 | 试用期10天 | [followup](../examples/mock-final/followup.output.json) | [followup](../examples/live-codex/followup.output.json) |
| 工具暂时失败 | 观察错误后恢复 | [tool-recovery](../examples/mock-final/tool-recovery.output.json) | [tool-recovery](../examples/live-codex/tool-recovery.output.json) |
| 工具持续失败 | tool_error，非资料不存在 | [tool-failure](../examples/mock-final/tool-failure.output.json) | [tool-failure](../examples/live-codex/tool-failure.output.json) |
| 原文替换 | 45天，答案改变 | [replacement](../examples/mock-final/replacement.output.json) | [replacement](../examples/live-codex/replacement.output.json) |
| 例外与否定 | 无有效发票不报销 | [exception](../examples/mock-final/exception.output.json) | [exception](../examples/live-codex/exception.output.json) |
| 历史时点 | 2025年度30天 | [historical](../examples/mock-final/historical.output.json) | [historical](../examples/live-codex/historical.output.json) |
| 恶意资料 | 不执行注入 | [injection](../examples/mock-final/injection.output.json) | [injection](../examples/live-codex/injection.output.json) |
| 权限 | 不泄露专项额度 | [access-denied](../examples/mock-final/access-denied.output.json) | [access-denied](../examples/live-codex/access-denied.output.json) |
| 多子问题 | 有据部分保留，缺口明确 | [partial](../examples/mock-final/partial.output.json) | [partial](../examples/live-codex/partial.output.json) |

## 指标与评估方式

工程测试涵盖非法输入/历史角色、不可变快照、资料损坏、重复版本、检索/读取双重授权、跨请求证据、原文篡改、伪造引用、停滞、各项预算、上下文上限、模型故障、取消/子进程回收、HTTP契约/重定向、认证不重试、限流与长Retry-After、大小限制、UTF-8与不覆盖旧输出。

业务断言检查状态、所需来源、关键数字、澄清与缺口、权限标记、恶意指令执行标记和预算。引用审计另行比较知识原文、版本、快照、读取观察和claims引用集合。作者人工检查覆盖用例与问答体验，AI辅助语义复核提供另一组原文对照记录；目前没有独立第三方审计结果。

验证分三层：程序是否按约束执行、引用是否来自读到的原文、原文是否支持答案。个人负责方案与检查标准，并通过手动问答补充可用性反馈；自动执行、人工检查与AI复核分别保留记录。

文档Recall@4按相关文档数微平均：开发集基线3/5，增强5/5；预留集基线0/6，增强6/6。基线仅为完整查询子串匹配，很弱；语料小、标注由同一开发过程构造，不是独立真实测试集。该结果不能证明优于成熟检索器，也不报告未经测量的精确率。预留集第一次测量后没有据此调整检索算法；它仍不能称为外部盲测。

Recall@4的意思是：只看前4个检索结果，应当找到的文档找回了多少。例如5/5表示这个小型样本中5份应找回的文档都找到了，不是“所有企业问题准确率100%”。

Mock耗时为本地模拟开销，不能当作大模型延迟。真实耗时、调用次数和可取得的usage记录在每份metadata中，样本少不报告稳定P95或线上SLO。真实模型使用可替换的本机配置，公开结果仅保留匿名模型别名，未披露可公开确认的服务端模型ID；这限制逐模型的精确复现与横向比较。

## 失败、修复与环境差异

1. Windows受管文件系统不允许hardlink，改为Windows同目录无覆盖rename，POSIX保留无覆盖link；有不覆盖旧结果测试。
2. 沙箱系统临时目录阻塞，改用忽略的.local/tmp；本地回环HTTP在受限沙箱失败，在获准的普通开发环境执行通过，不静默跳过。
3. tuple序列化为list被误判为脱敏，导致业务检查失败；修复为比较JSON规范化内容，之后回归通过。
4. CLI非致命诊断被误判为工具执行；修正分类，仍要求成功turn、有效JSON和无额外工具事件，增加负向回归。
5. 真实独立请求未继承Windows代理环境，先后出现60/120/90秒超时，见 [首次](../examples/live-codex-smoke/normal.output.json)、[第二次](../examples/live-codex-smoke-v2/normal.output.json)、[模型选择重试](../examples/live-codex-configured/normal.output.json)。仅在验证进程中使用操作者现有代理与模型选择后，真实正常链路通过。没有修改系统代理或复制认证资料。
6. 极低预算时，模型曾未检索即返回资料不足，见 [初次记录](../examples/engineering/live-budget-initial.output.json)；仅有检索但预算不够读取时，也曾误归类资料不足，见 [第二次记录](../examples/engineering/live-budget-second.output.json)。新增约束：资料不足必须有成功检索观察，工具失败必须有错误观察，工具预算耗尽不能归类知识缺失。新增3项回归，真实重新验证返回incomplete/tool_limit，并验证原14条真实决策在新约束下回放通过。回放不冒充模型重跑。
7. 首次远端CI发现Linux取消测试失败，Windows两版本通过。原测试全局替换time.sleep，影响POSIX的subprocess.wait回收等待；改为只注入项目自己的pause边界，避免故障注入同时破坏清理机制。CI同时保留脱敏失败注解并关闭矩阵fail-fast，便于看到全部平台差异。初次及定位运行见公开Actions历史，最终以最新提交检查为准。

早期mock、verification-v1、verification-final、verification-release等目录是实际历史记录，不代表最终发布统计；默认看mock-final、verification-cross-platform-fix与完整live-codex目录。所有失败和重跑均不伪装为一次通过。

## 已知限制

- 小型中文合成制度、有限同义词与少量真实运行，不证明广泛业务质量；尚无独立第三方语义审计或大规模用户验证。
- 逐项证据关系与原文核对能防伪造，不能自动证明结论语义支持或覆盖所有子问题。
- CLI访问范围由可信本机操作者配置，不是SSO、多租户网络隔离或可对外暴露的服务认证。
- Codex用于受控合成验证，事件检查是额外防线，不应把账号CLI直接提供给不可信远程用户；HTTP后端只接受结构化决策，不暴露任意业务工具。
- 超长历史/片段明确拒绝，不做自动摘要、分页式超长文档接入或企业同步。
- API后端已验证受控真实HTTP传输与契约，未使用商业API密钥做在线模型验收；真实模型记录来自Codex。
- Python3.11语法检查通过；Python3.11及Linux实际运行通过远端CI单独核对，不能把矩阵配置或本机Windows结果代替远端结果。
- 未做真实负载、并发容量、分布式可用性、企业资料审批或持续安全红队测试。

## 投入预算与实际用时

首版代码开发的时间预算为约2小时，方案、验证、人工体验和文档整理的总体投入上限目标为4小时。预算用于范围控制，与已经测量的实际区间分开记录；纯编码阶段没有独立计时。

[worklog.json](../examples/engineering/worklog.json)记录首轮开发开始时间和77.52、92.37分钟两个检查点。根据首次成功CI四个任务的公开完成时间，首轮开发与技术验证区间为北京时间2026-11-02 17:43:48至19:16:57，共93.14分钟，包含编码、调试、真实模型等待、推送和CI排查。

方案制定、人工检查、手动问答及后续文档整理未独立计时，因此暂不提供完整总工时或纯编码实际工时。真实评估与重复验证的进程时长存在短暂重叠，不能直接相加。原始计时检查点保持不变，后续工作按同一口径补充记录。
