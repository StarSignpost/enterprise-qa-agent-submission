# 企业知识问答 Agent（第 3 题）

Python CLI、本地 JSON 合成制度、检索与原文读取工具、真实模型循环、独立离线 Mock、调用上限、引用核验与结构化 Trace。真实服务现仅保留 **DeepSeek Responses / deepseek-flash**，没有同时接入第二家服务。

2026-11-01 已真实运行正常、冲突、资料外、改写、上下文及工具故障等场景，阶段记录见[原真实评估报告](examples/real/deepseek-2026-11-01/README.md)。最新增量为一个报销短语映射，前后基线和三组真实对照见[改进报告](examples/improvements/synonym-001/README.md)，评估汇总见[03-evaluation](docs/03-evaluation.md)。旧失败与原始Trace保留，结果不保证每次复现完全一致。

## 环境与离线验证

Python 3.10+，仅标准库，无需安装第三方库；本机实际版本为 Python 3.10.0。运行目录为项目根目录。`requirements.txt` 说明依赖边界。

本工作区的 PowerShell 请先切换到项目目录，再运行后续命令：

```powershell
Set-Location -LiteralPath 'E:\temp2'
python -m unittest tests.test_tools -v
```

AI已在该目录实际执行以上工具测试命令，22项通过；从个人目录运行会找不到本项目模块。用户首次执行的模块加载失败与修正后的复核状态见[用户复核记录](examples/improvements/synonym-001/review-command-fix/user-attempt-01.json)。


已执行：

```powershell
python -m tests.run_validation --output-dir examples/improvements/synonym-001/offline
```

结果为 **70 项离线通过，12 项真实测试在该离线报告中明确未运行**，总发现 82 项。见[逐项报告](examples/improvements/synonym-001/offline/test-report.json)。本次词条增量真实运行3组（修改前1、修改后2），另有独立报告；旧十项真实样本对应修改前源码，不能跨版本算作当前全部通过。不能把本报告的跳过算成通过。协议单测使用内存 HTTP 替身，离线运行器阻止 provider 联网。

重跑请用新的输出目录，例如（该新目录命令尚未执行）：

```powershell
python -m tests.run_validation --output-dir examples/checks/manual-001
python -m src.cli --mode mock --mock-script tests/fixtures/mock_actions/normal.json --data data/scenarios/normal.json --input examples/inputs/normal.json --max-steps 8 --output-dir examples/mock/manual-001
```

Mock 的动作和语义复核结论来自 `tests/fixtures/mock_actions/` 脚本，业务工具仍实际执行；它只验证工程流程，不证明模型的自主判断或真实业务质量。

## 真实运行

接口依据 [DeepSeek Responses 官方文档](https://api-docs.deepseek.com/guides/responses_api/)与[工具调用文档](https://api-docs.deepseek.com/guides/tool_calls/)。端点为 `https://api.deepseek.com/responses`，本次模型为 `deepseek-flash`，配置 `reasoning.effort=none`，默认上限 8 次模型请求，复核和无效响应也计数。服务端不保证单动作，程序在本地校验；收到多个动作时整批拒绝并反馈模型，完整保留记录。

可用隐藏输入运行真实六项验收（下面的新目录命令未执行，实际命令见各报告的 `invocation.json`）：

```powershell
python -m tests.run_private_live --model deepseek-flash --output-dir examples/real/manual-001
```

程序提示输入密钥，不回显、不保存；仅在该进程环境中传递。追加 `--test tests.test_live.LiveBoundaryTests` 可单独运行资料变更、表述不足、触顶及无相关资料四项补充检查。网络、账号和额度须可用；本机默认受限进程曾报 Windows 10013，获准联网的运行实际成功。普通终端需具备对应联网权限。

单轮 CLI 从进程环境读取 `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`；在可信本机方式配置后可运行：

```powershell
python -m src.cli --mode real --data data/scenarios/normal.json --input examples/inputs/normal.json --max-steps 8 --output-dir examples/real/cli-manual-001
```

`.env.example` 仅列变量与公开模型标识，程序不自动加载 `.env`。不要把密钥加入命令行、代码、日志或提交材料。真实配置或 API 失败明确返回失败，不降级 Mock。

## 模型循环与证据

输入为 `question` 和可选有序 `history`（user/assistant 文本）；历史最多 20 条、输入总计最多 20,000 字符。每次 CLI 处理一个用户轮次，追问时传入前轮实际问答。

每轮模型收到用户问题、历史、工具定义、已有真实观察和剩余额度，自主选择 `search_documents`、`read_document`、`clarify`、`answer` 或 `stop`。程序校验和执行后，把成功或明确错误结果以原 `call_id` 的 `function_call_output` 放入下一请求，再由模型决定。

- 两个业务工具：检索返回 ID、版本日期、标题、摘要与词项分数；原文读取返回可核验的 Unicode 起止位置、片段和可信读取句柄。搜索摘要不能替代原文引用。
- 数据在 `data/scenarios/`，包含正常、冲突、无相关、表述不足和确定性工具故障；场景只改变资料或故障，不配置模型动作或答案。
- 引用先检查本轮成功读取、ID、版本、偏移和逐字片段，再通过同一模型的独立 `assess_answer` 请求检查语义支持及遗漏冲突。两个检查不同；模型复核仍可能误判。
- 不按日期裁决 30/15 天冲突，不把常识补成公司规定。无效动作和复核均消耗可配置上限，触顶明确 `incomplete`，不额外生成“成功总结”。
- 输出包括回答、引用、缺口、状态、模式、模型、计数、终止来源和核验结果。`completed`、`needs_clarification`、`incomplete`、`failed` 分开表达。

每次输出目录必须尚不存在，避免覆盖旧证据。目录保存 `input.json`、`output.json`、`trace.jsonl`、`run.json`、`documents.json`，含实际日期/时区、命令、配置、源码哈希和资料快照。Trace 记录工具参数、实际返回、摘要、后续真实动作和简要依据，不记录模型内部思维过程或认证头。

退出码：完成或需澄清为 0，未完成为 2，失败为 1；退出码 0 不代表已回答，应核对 `status`。文件为 UTF-8；终端输出使用 ASCII JSON 转义以兼容 Windows。

## 交付范围与限制

需求矩阵见 [01-requirements](docs/01-requirements.md)，调用流程与职责见 [02-solution](docs/02-solution.md)，预期/实际/失败与缺口见 [03-evaluation](docs/03-evaluation.md)。轻量同义词与中文双字检索可能漏召回或误召回，不能据分数推断权威。真实测试检查事实、引用和状态，不要求逐字措辞或唯一动作顺序；单次样本与同模型复核不证明普遍可靠性。

尚未做干净环境复现、最终 GitHub 仓库提交及评审权限验证；AI 使用独立说明、最终复盘与完整交付核对仍待后续指定阶段。本轮实现、测试、执行和报告由 AI 辅助完成；用户确定范围并选择服务、提供临时认证配置，不编造用户手工编码、测试或工时。原始卷面及其个人信息保持排除，不提交密钥。
