# DeepSeek 真实模型验收记录

日期：2026-11-01（Asia/Shanghai）。Python 3.10.0，服务 DeepSeek，实际模型 `deepseek-flash`，运行模式 `real`，端点 `https://api.deepseek.com/responses`，`reasoning.effort=none`，`max_output_tokens=3000`，默认请求上限 8 次。认证仅经隐藏输入进入进程内存，不写入项目。

六项业务及四项补充检查，**按测试 ID 取最新结果为 10 项通过**。实际共执行 12 个测试实例：10 通过、2 失败；初始失败均保留。累计 14 份真实证据包、67 次模型请求，包含失败、无效动作和语义复核，不代表首次全部成功或稳定性统计。取模型列表的预检不计入这 67 次。

机器可读汇总见 [summary.json](summary.json)，保存证据审计见 [audit.json](audit.json)。每个目录均包含实际 `input.json`、`output.json`、`trace.jsonl`、`run.json`、`documents.json`；`run.json` 记录本次原始 CLI 命令、配置、日期和源码哈希。外层 `invocation.json` 是实际隐藏输入运行命令。

## 最新用例与实际结果

“请求数”包括校验错误后的修正和支持复核；`failed` 是工具故障场景的正确业务终态，测试本身通过。

| 检查 | 实际输出与状态 | 请求数 | 完整证据目录 |
| --- | --- | --- | --- |
| B01 明确答案 | 回答 30 天，引用 D01，`completed`。 | 4 | [normal](normal-fixed/cases/real/test_b01_clear_answer/normal/) |
| B02 文档冲突 | 列出 D01 30 天、D02 15 天，缺适用范围及优先级，请求确认，`needs_clarification`。 | 5 | [conflict](business/cases/real/test_b02_conflicting_documents/conflict/) |
| B03 资料外 | 找到部分报销文档后读取，说明不能确定宠物医疗费报销范围，`incomplete`。 | 6 | [outside](business/cases/real/test_b03_outside_corpus_with_partial_keyword_hits/outside/) |
| B04 原问/改写 | 两次独立会话均回答 30 天，引用 D01，`completed`。 | 4 + 4 | [original](business/cases/real/test_b04_paraphrase_preserves_facts_and_sources/original/)、[paraphrase](business/cases/real/test_b04_paraphrase_preserves_facts_and_sources/paraphrase/) |
| B05 首轮/追问 | 首轮对差旅适用范围保留缺口并澄清；第二轮使用其实际问答历史，重读 D03，回答发票和出差审批单，`completed`。 | 7 + 5 | [first](follow-up-fixed/cases/real/test_b05_context_follow_up/first/)、[follow-up](follow-up-fixed/cases/real/test_b05_context_follow_up/follow-up/) |
| B06 工具故障 | 两次读取均收到 `TOOL_UNAVAILABLE`，最后说明失败，`failed`，无成功引用。 | 5 | [failure](business/cases/real/test_b06_tool_failure_has_explicit_cause/failure/) |
| 资料变更对照 | 仅把 D02 正文的 15 改为 30，其余文档/日期、输入、模型、上限相同；读取双方后回答一致的 30 天，`completed`。 | 7 | [same-deadline](follow-up-fixed/cases/real/test_conflict_content_change/same-deadline/) |
| 问题表述不足 | “多久？”具体追问事项和可能影响口径的字段，`needs_clarification`。 | 1 | [ambiguous](follow-up-fixed/cases/real/test_underspecified_question/ambiguous/) |
| 真实执行上限 | 上限设 1，请求检索后预算用尽；未额外生成答案，`incomplete / EXECUTION_LIMIT`。 | 1 | [limit](follow-up-fixed/cases/real/test_execution_limit/limit/) |
| 无相关资料 | 模型自行改写三次检索均零结果，再明确资料缺口，`incomplete`。 | 5 | [no-match](follow-up-fixed/cases/real/test_no_related_documents/no-match/) |

每个表项的原文、完整措辞、真实调用参数及错误以证据包为准。以上不要求逐字回答或唯一顺序。部分运行出现多动作或未知动作，程序确实拒绝并交回错误，模型之后修正；没有删掉这些记录，也不把被拒动作记成已执行工具。

## 不同工具结果后的真实路径

1. [正常 Trace](normal-fixed/cases/real/test_b01_clear_answer/normal/trace.jsonl)：第 1 步检索；第 2 步读取 D01 得到“报销期限 30 天。”及可信读取句柄；模型第 3 步选择回答并引用该句柄；第 4 步独立 `assess_answer` 返回 supported，完成。
2. [冲突 Trace](business/cases/real/test_b02_conflicting_documents/conflict/trace.jsonl)：第 1 步实际返回多动作，整批拒绝；第 2 步模型选择检索，实际结果同时含 30/15 天；模型第 3、4 步分别读取 D01、D02 原文查证；第 5 步列双方证据并请求确认。**本次没有在读取双方后额外搜索**，不能把示例“补查”写成发生了额外检索。继续查证表现为读取双方原文，最终未按日期更新裁决。
3. [故障 Trace](business/cases/real/test_b06_tool_failure_has_explicit_cause/failure/trace.jsonl)：检索 → 读取实际失败 → 模型选择再次检索 → 模型再次读取仍失败 → 模型选择停止并报告 failed。补查和重试来自新的模型动作，程序没有自动重试读取。

`tool_result` 保存执行结果及摘要；下一 `model_request.observation_call_ids` 关联观察；`transition` 在后续真实动作发生后才追加动作及简要依据。适配器通过 `function_call_output` 把实际完整结果送入下一 HTTP 输入，协议单测检查载荷回传。保存日志不是独立网络抓包，需结合实现核对。

资料变更对照的两份 `documents.json` 已比较：只有 D02 的正文不同，问题/历史/上限相同。旧资料结果为需澄清，新资料结果为完成，证明本批样本对实际资料变化有响应；不是确定性脚本选择动作。

## 失败、原因与修正

- [smoke/test-report.json](smoke/test-report.json)：首个正常测试真实失败，7 次请求。模型取得原文后猜测读取句柄，引用核验拒绝两次，最后模型报告失败。没有放宽核验，也没有修改这次 Trace。修正在 `src/agent.py` 成功读取结果中显式提供可信 `read_call_id`，引用错误反馈只提供实际读取句柄；提示要求逐字复制。两项回归及相关检查通过后，[normal-fixed](normal-fixed/test-report.json)真实重跑通过（4 次）。
- [business/test-report.json](business/test-report.json)：5 项中 4 通过、1 失败。失败位于 B05 的首轮断言：测试强制要求“差旅报销期限”首轮 completed，但合成资料没明确差旅适用范围。模型实际保留缺口并停止，不能为测试补造范围或删缺口。只调整测试：允许首轮如实保留未完成/澄清，仍要求 D01 真实引用，再将实际输出放进历史检查第二轮；材料回答仍须 completed、引用 D03。更新后的离线测试通过；[follow-up-fixed](follow-up-fixed/test-report.json)真实重跑及四项补充均通过。
- 默认受限进程曾连接失败（Windows 10013）；获准联网的进程实际取得真实响应。该网络限制与认证无效不同。本批成功包无 API 降级或替换 Mock。

修复前 `smoke` 的源码哈希与当前不同，其余 13 包的 `src/` 哈希与当前一致。B05 测试断言修正前后的测试哈希不同，各批报告保留当时版本；不重写旧报告来统一哈希。

## 已执行命令与复现

以下三条均已实际执行，输出目录禁止覆盖；命令不含认证信息，运行时隐藏输入：

```powershell
python -m tests.run_private_live --model deepseek-flash --output-dir examples/real/deepseek-2026-11-01/normal-fixed --test tests.test_live.LiveAcceptanceTests.test_b01_clear_answer
python -m tests.run_private_live --model deepseek-flash --output-dir examples/real/deepseek-2026-11-01/business --test tests.test_live.LiveAcceptanceTests.test_b02_conflicting_documents --test tests.test_live.LiveAcceptanceTests.test_b03_outside_corpus_with_partial_keyword_hits --test tests.test_live.LiveAcceptanceTests.test_b04_paraphrase_preserves_facts_and_sources --test tests.test_live.LiveAcceptanceTests.test_b05_context_follow_up --test tests.test_live.LiveAcceptanceTests.test_b06_tool_failure_has_explicit_cause
python -m tests.run_private_live --model deepseek-flash --output-dir examples/real/deepseek-2026-11-01/follow-up-fixed --test tests.test_live.LiveAcceptanceTests.test_b05_context_follow_up --test tests.test_live.LiveBoundaryTests
```

首个失败 smoke 命令见其 [invocation.json](smoke/invocation.json)。换新目录可复现当前六业务检查。若要在一条新命令中选择全部十项，需同时指定 `--test tests.test_live.LiveAcceptanceTests --test tests.test_live.LiveBoundaryTests`；该组合入口本轮未单独整批执行，各项实际分批执行如上。真实输出可能变化。完整元数据包括各批起止日期，不把模型请求耗时当作用户个人工时。

离线最终执行 `python -m tests.run_validation --output-dir examples/checks/deepseek/acceptance-final`：68 通过，10 真实测试在该批未运行，见[实际报告](../../checks/deepseek/acceptance-final/test-report.json)。不存在 ID、错误片段、未读区间、假成功及语义复核拒绝等确定性边界通过 Mock 验证，不能改名为真实模型对抗证据。

## 原题核对与剩余缺口

B01—B06 六项、真实模型循环、至少两条结果导致不同后续动作的路径、调用上限、三类完整材料、真实/Mock 模式分开、结构化 Trace 与原文引用在本批已有证据。输入表述不足和资料变更对照也已真实执行。AI 对照合成资料逐条核对事实：30 天对应 D01；冲突保留双方；材料来自 D03；资料外及故障没有给出已查明的制度结论。代码片段核验与同模型支持复核是不同检查；此处核对由 AI 完成，没有独立人工签署。

尚未验证或完成：干净环境复现、重复稳定性/大样本质量、独立人工语义评审、真实模型故意伪造 ID/片段的对抗实验、独立 AI 使用说明与最终复盘、实际 GitHub URL/完整 commit SHA/评审权限。没有建立或提交仓库，不宣称全部交付完成。

本轮模型适配、循环修正、测试、运行及报告由 AI 辅助完成；用户限定范围、给出验收和服务配置。没有证据表明用户手工修改代码或亲自运行测试，不编造个人贡献、经历或用时。认证值、原题个人信息均不写入这些材料；临时认证应由持有人在完成验证后撤销。

## 本轮修改文件

- `src/models.py`、`src/cli.py`：唯一真实服务改为 DeepSeek，按官方 Responses 能力构造请求，调整环境变量和公开运行元数据。
- `src/agent.py`、`src/prompts.py`：实际读取结果显式提供可信句柄；错误反馈只列成功读取；保留被拒多动作记录，提示复制真实引用句柄。
- `tests/test_models.py`、`tests/test_agent.py`：DeepSeek 协议单测及句柄可见性/错误反馈回归。
- `tests/acceptance_support.py`、`tests/test_live.py`：上下文首轮断言纠正、四项真实补充检查；新增 `tests/run_private_live.py` 以隐藏输入传递认证。
- `.env.example`、`requirements.txt`、项目 `README.md`、`docs/01-requirements.md`、`docs/02-solution.md`、`docs/03-evaluation.md`：更新配置、运行与实际验收，历史事实保留并注明阶段。
- `examples/checks/deepseek/`、本真实根目录：新增实际离线报告、失败/重跑的真实证据、汇总与审计；没有改写旧 Trace、旧输出或资料快照。
