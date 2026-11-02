# 运行与故障排查

需要Python 3.11+，无第三方运行依赖。实际验证的平台见评估，不把CI配置当作CI已经通过。所有命令在仓库根目录执行。

下面每个代码块是一项独立操作，不需要一次复制全部命令。第一次使用可先按 [README](../README.md) 的编号步骤操作。

检查配置与资料能否正常加载：

```text
python -m src.main --doctor
```

模拟正常提问：

```text
python -m src.main --input examples/cases/normal.input.json
```

模拟两份制度冲突：

```text
python -m src.main --input examples/cases/conflict.input.json --corpus data/corpora/conflict.json
```

模拟一次暂时的检索失败：

```text
python -m src.main --input examples/cases/normal.input.json --fault search:once
```

把业务工具调用限制为1次，观察明确的未完成状态：

```text
python -m src.main --input examples/cases/normal.input.json --max-tools 1
```

运行完整离线场景并保存记录：

```text
python -m src.evaluate --backend mock --output .local/my-evaluation
```

评估输出目录必须是新目录。单次 --output 文件不能已存在，避免覆盖旧证据；标准输出为单个JSON。doctor只检查配置和资料，不验证认证或连通性。

## 用户自配模型

API由操作者在环境中设置AGENT_MODEL、AGENT_API_BASE、AGENT_API_KEY；程序不自动加载.env。不要把密钥写进命令参数、脚本或提交记录。

```text
python -m src.main --backend api --input examples/cases/normal.input.json
```

用API模型运行完整场景：

```text
python -m src.evaluate --backend api --output .local/my-api-evaluation
```

用本机Codex模型运行一次提问：

```text
python -m src.main --backend codex --input examples/cases/normal.input.json
```

用本机Codex模型运行完整场景：

```text
python -m src.evaluate --backend codex --output .local/my-codex-evaluation
```

Codex需要使用者自己的CLI及登录，AGENT_CODEX_BIN可指定执行文件，--model可指定自己可用的模型。项目不调用登录、不读取凭证、不更改已有认证；默认模型不可确认时明示未披露。

若Windows已启用代理而独立进程仍超时，确认当前进程的HTTPS_PROXY/HTTP_PROXY及NO_PROXY设置。项目不复制系统代理地址；验证时仅临时复用现有设置，不能把本机网络配置提交。隔离模式忽略用户默认模型，应通过--model显式指定。

通过完整回归后可用 --cases normal,conflict,outside --repeat 2 做少量稳定性验证，不代表线上可靠性统计。

## 状态与错误

| 状态 | 含义与处理 |
| --- | --- |
| input_error，退出2 | 修正JSON、字段、日期或长度 |
| configuration_error，退出3 | 检查自己的模型、密钥环境变量或CLI安装 |
| io_error，退出4 | 检查资料与输出路径；使用新输出文件 |
| answered | 依据已读资料回答，注意引用与适用范围 |
| needs_clarification | 根据追问补充适用条件或制度优先级 |
| insufficient_evidence | 当前可访问资料不足，应补资料，不代表企业没有制度 |
| tool_error | 工具不可用，恢复后重跑 |
| model_error | 认证、限流、模型协议或能力问题，按reason_code排查 |
| incomplete | 超时、上限、停滞或取消，查看原因，缩小问题或合理调整预算 |

业务终态由JSON表达，成功输出业务结果时CLI退出0；评估只要有不符合预期的场景即退出1，不能只看单次CLI退出码认定验收通过。

Ctrl+C取消时仅回收本次子进程。临时文件位于忽略的.local/tmp，避免受限系统临时目录阻塞；无覆盖原子写入完成后才公布结果。

真实资料不宜直接作为公开示例。Trace只导出应用允许字段；export_redacted=true表示导出内容有替换，不能作为逐字原文引用完整性的通过证据。原始供应商响应、异常堆栈、Codex会话流不保存到提交材料。

## 复现与发布

```text
python -m unittest discover -s tests -v
```

运行相同工程测试并保存报告：

```text
python scripts/verify.py --output .local/my-verification
```

检查文件完整性和疑似私密内容：

```text
python scripts/check_release.py
```

核对已保存的引用是否与原始资料一致：

```text
python scripts/audit_examples.py examples/mock-final --output .local/my-provenance-audit.json
```

将保存的真实决策放入当前运行时回放，检查兼容性；这一步不重新调用模型：

```text
python scripts/replay_traces.py --output .local/my-replay.json
```

受限沙箱可能禁止本地HTTP回环测试，应在获准的普通开发环境执行并记录，不能静默跳过。CI无须个人凭证。隐私扫描为启发式检查，仍需核对源代码、材料和Git历史。
