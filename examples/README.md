# 验证材料

`cases/`保存合成输入与独立预期，不进入模型上下文。

| 目录 | 用途 |
| --- | --- |
| mock-final/ | 最终14组Mock实际输出，明确标记模拟决策 |
| live-codex/ | 完整14组真实Codex业务验证，脱敏输入、输出、Trace和汇总 |
| live-codex-repeat/ | 冲突与资料外问题各额外2次真实运行 |
| clean-submission/ | 最终源码在无pip干净虚拟环境中的14组实际输出 |
| engineering/ | 发布前50项测试、原文审计、AI语义复核、预算边界、决策回放、用时记录 |
| live-codex-proxy-smoke/ | 恢复代理环境后的真实正常路径 |
| live-codex-smoke/、smoke-v2/、configured/ | 早期真实网络超时记录，名称完整前缀均为live-codex- |
| mock/、clean-environment/ | 较早的实际运行记录，保留作过程证据 |

最新本机发布测试为engineering/verification-cross-platform-fix/tests.json；先前verification-*为历史记录。跨平台执行结果核对最终提交的GitHub Actions。以 [评估文档](../docs/03-evaluation.md) 的入口为准。

作者已完成用例检查与手动问答体验，摘要见 [人工检查记录](../docs/09-manual-validation.md)。AI复核JSON保留自身来源标记；决策回放不是新的真实模型验证。原始供应商事件、账号配置、代理地址和认证材料不保存在这里。
