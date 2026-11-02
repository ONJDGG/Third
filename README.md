# Enterprise Evidence Agent

企业制度知识助手。模型自主检索、读取、查证冲突或追问，运行时负责权限、证据和执行预算。资料为合成报销制度，无真实企业数据。

例如，员工问“境内差旅报销期限多久”，程序会查找制度、读取原文，再给出答案与出处；如果两份制度分别写30天和15天，又没有优先级依据，就说明冲突并追问，不替企业猜一个答案。

我负责总体方案、工程要求、人工检查测试用例，并手动模拟用户问答、提出优化建议。AI主要承担编码执行及部分技术建议。具体分工见 [个人贡献](docs/04-ai-usage.md)，使用反馈见 [人工体验](docs/09-manual-validation.md)，能力证据见 [验收说明](docs/08-acceptance.md)。

Python 3.11+，无第三方运行依赖，默认Mock离线入口不需账号或密钥。真实模型结果与Mock明确区分；实际验证状态见 [评估](docs/03-evaluation.md)，不以Mock通过证明真实决策质量。

本机验证：50项工程测试、14组Mock场景、14组真实Codex场景及4次真实重复测试通过；真实工具预算验证返回incomplete。另有干净环境复现、原文审计、作者人工用例检查和手动问答体验。AI辅助复核记录保留原来源；当前结果不代表第三方审计或线上整体准确率。

## 快速运行

以下按步骤操作，每次只复制一个代码块，使用同一个终端窗口。默认使用离线Mock，不需要登录或配置密钥。

**第1步：获取项目。** 已有项目文件时，可直接在项目根目录打开终端，从第3步开始。

```text
git clone https://github.com/ONJDGG/Third.git
```

**第2步：进入刚下载的项目目录。**

```text
cd Third
```

**第3步：检查Python版本。** 需要3.11或更高版本，没有第三方运行依赖，无须额外安装Python包。

```text
python --version
```

**第4步：模拟一次员工提问。** 输入文件里的问题是“境内差旅报销期限多久？”

```text
python -m src.main --input examples/cases/normal.input.json
```

应看到`answer`包含30天、`status`为`answered`，`citations`附上D01原文。这是Mock的实际流程运行，不是一次真实模型调用。

**第5步：模拟资料冲突。** 问题相同，但换成包含两份冲突制度的资料。

```text
python -m src.main --input examples/cases/conflict.input.json --corpus data/corpora/conflict.json
```

应同时说明30天与15天，状态为`needs_clarification`，并请求确认适用制度。

**第6步：运行工程测试。**

```text
python -m unittest discover -s tests -v
```

成功时末尾显示`Ran 50 tests`和`OK`。

**第7步：运行14组离线场景并保存记录。**

```text
python -m src.evaluate --backend mock --output .local/review-evaluation
```

每组应显示`passed: true`，结果汇总在`.local/review-evaluation/summary.json`。输出目录不能已经存在；再次运行时换一个目录名。

结果中的`answer`是回答，`citations`是原文依据，`gaps`是缺少的资料或条件，`status`是当前结果状态；`claims`是关键结论，`trace`是逐步工作记录。模拟持续工具故障等更多操作见 [运行手册](docs/06-operations.md)。

--output可保存单次结果，文件不能已存在；评估输出目录需为新目录。CLI stdout只有JSON，错误诊断进入stderr。业务未完成也输出状态；评估失败返回非零退出码。

## 选择模型

- `--backend mock`：默认，确定性流程模拟，不证明真实模型能力。
- `--backend api`：Chat Completions 严格JSON Schema协议子集，配置AGENT_MODEL、AGENT_API_BASE、AGENT_API_KEY。参考 [.env.example](.env.example)，程序不自动加载.env。
- `--backend codex`：可选本机CLI适配器，使用操作者自己的现有登录，不读取或分发认证资料。可通过--model指定可用模型。

```text
python -m src.main --backend codex --input examples/cases/normal.input.json
```

执行完整API模型验证：

```text
python -m src.evaluate --backend api --output .local/real-api-evaluation
```

执行完整Codex模型验证：

```text
python -m src.evaluate --backend codex --output .local/real-codex-evaluation
```

真实后端失败不会静默变成Mock。建议先运行 --doctor 检查配置，再执行正常场景做连通性检查。doctor不发模型请求，也不检查账号凭证。

若网络依赖本机代理，需由操作者在当前进程环境设置HTTP_PROXY、HTTPS_PROXY和适当的NO_PROXY；Windows系统代理不一定自动被独立CLI采用。真实地址只留在本机，不写入仓库。Codex隔离模式不加载用户默认模型，必要时用--model显式指定可用模型。

## 工程特点与文档导航

| 检查内容 | 入口 |
| --- | --- |
| 业务范围、输入输出与成功标准 | [需求](docs/01-requirements.md) |
| 功能核对、两条真实决策路径 | [能力验收与证据](docs/08-acceptance.md) |
| 动态决策、权限、知识快照、证据 | [方案](docs/02-solution.md)、src/agent.py、src/tools.py |
| 真实结果、失败、限制、检索对比 | [评估](docs/03-evaluation.md)、examples/ |
| AI辅助与实际验证责任 | [AI使用](docs/04-ai-usage.md) |
| 取舍、学习与改进 | [复盘](docs/05-retrospective.md) |
| 配置、退出码、故障恢复 | [运行手册](docs/06-operations.md) |
| 工程风险与优先级 | [开发计划](DEVELOPMENT_PLAN.md) |
| 作者手工检查与使用反馈 | [人工检查与问答体验](docs/09-manual-validation.md) |

本项目提供本地访问策略测试，`--groups`是可信本机操作者设置的合成访问范围，不是身份认证。默认只读业务工具；没有线上部署、SSO、多租户服务、向量数据库或写操作。提示注入和自然语言语义支持不能由有限测试证明完全安全或正确。

## 验证与交付

```text
python scripts/verify.py --output .local/my-verification
```

检查拟交付材料是否缺文件、是否含疑似私密信息：

```text
python scripts/check_release.py
```

固定合成输入及预期见 [manifest](examples/cases/manifest.json)。预期由评估程序读取以对比结果，Agent运行时和模型上下文不接触这些预期。CI覆盖Windows/Linux及Python3.11/3.14的离线任务，具体执行状态见 [GitHub Actions](https://github.com/ONJDGG/Third/actions/workflows/offline.yml)。

代码、资料、测试与说明均在 [ONJDGG/Third](https://github.com/ONJDGG/Third) 维护。公开材料不包含密钥、账号配置、认证缓存或私有原始日志。版本复现与打包见 [交付说明](docs/07-delivery.md)。

用下面的命令取得当前完整版本SHA：

```text
git rev-parse HEAD
```

投入预算、实际计时及未完成内容见 [评估报告](docs/03-evaluation.md)。首版采用CLI，网页界面、线上部署、多Agent及完整长文档接入作为后续演进方向。

项目按仓库已有的 [MIT许可证](LICENSE) 发布。
