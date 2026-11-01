# 第 3 题：测试与评估记录

日期：2026-11-01（Asia/Shanghai）。**最新单词条增量见第9节：70项离线通过，3组真实对照通过（旧词表1、新词表2）。** 第8节为上一完整真实阶段的六业务与四补充，原始失败保留；旧十项真实未在新词条下整批重跑。真实与离线跳过分开。

第 1—7 节是此前离线与缺配置阶段的历史快照，其中“未运行”、OpenAI 变量及当时缺口仅描述当时状态。当前仅保留 DeepSeek 真实适配器，运行方式以项目 README 和第 8 节为准。

## 1. 结果与边界

本次测试共发现 72 项：**66 项离线测试实际通过；6 项真实模型测试跳过，明确记为“未运行”**，最终失败 0、错误 0。不能写成“72 项全部通过”，也不能据此认定六项业务的真实模型验收已达标。

- 运行环境：Python 3.10.0，仅标准库。
- 实际完整命令：`python -m tests.run_validation --output-dir examples/checks/acceptance/full`，退出码 0。
- 未传 `--live`，沿用用户已确认的先离线验证决定；测试运行器拦截真实适配器的网络入口，所有保存用例 `api_calls` 为 0。
- 输出包含 18 组实际输入、实际输出、JSONL Trace、资料快照和运行元数据。测试在同一进程直接执行 CLI 入口 `main`；各 `run.json` 的命令是等价复现形式，不冒称另外执行了 18 条 shell 命令。
- 业务工具、真实/Mock 适配器、循环和校验的生产源码未改；本轮新增测试、报告入口，修正一个 Mock 示例的失败说明。

报告入口：

| 文件 | 用途 |
| --- | --- |
| [test-report.json](../examples/checks/acceptance/full/test-report.json) | 逐项实际通过/失败/错误/未运行结果、执行时间、来源哈希；真实与离线分层。 |
| [test-output.txt](../examples/checks/acceptance/full/test-output.txt) | 本次完整 unittest 原始输出，含 6 项真实测试的 skip 原因。 |
| [coverage.json](../examples/checks/acceptance/full/coverage.json) | B01—B06、补充边界与实际测试 ID、证据目录映射。 |
| [case-runs.jsonl](../examples/checks/acceptance/full/case-runs.jsonl) | 18 组实际入口调用的模式、状态、退出码和完整证据位置。 |

## 2. 六项业务验收映射

下表“通过”仅指受控 Mock 与工程核对。模型动作和语义复核结论仍由脚本给出，不证明真实模型会采取这些动作。每个目录含 `input.json/output.json/trace.jsonl/run.json/documents.json`。

证据根目录为 `examples/checks/acceptance/full/cases/mock/`；表内给出其下的准确目录。未将旧记录改名为新结果。

| 编号 | 输入与预期 | 本次实际（离线） | 证据目录 | 真实模型 |
| --- | --- | --- | --- | --- |
| B01 明确答案 | 报销期限多久；D01 为 30 天。回答事实、引用和状态正确。 | 通过：`completed`，D01 原文引用可复核，支持复核为 Mock。 | `test_b01_clear_answer/normal/` | 未运行 |
| B02 冲突 | D01 30 天，较新 D02 15 天，无范围和优先级。保留双方并澄清。 | 通过：读取双方、补查后 `needs_clarification`，两份引用保留。未因日期选择 15 天。 | `test_b02_conflicting_documents/conflict/` | 未运行 |
| B03 资料外 | 问宠物医疗费报销；资料只有期限和差旅材料。即使部分关键词命中也不能当作足够证据。 | 通过：检索确有部分候选，但最终 `incomplete`，列出缺口。无结果场景另由工具测试覆盖。 | `test_b03_outside_corpus_with_partial_keyword_hits/outside/` | 未运行 |
| B04 相似改写 | 原问和“费用报销最迟得在多少天内办？”各自独立运行。 | 通过：两次均有 30 天事实和 D01 引用，未比较全文措辞或强制唯一顺序。 | `test_b04_paraphrase_preserves_facts_and_sources/original/` 与 `paraphrase/` | 未运行 |
| B05 上下文 | 第一轮差旅期限；第二轮“那需要什么材料？”，携带第一轮实际 Mock 输出。 | 通过：第二轮历史完整、`completed`，D03 引用含发票和出差审批单。只验证传递机制及脚本结果。 | `test_b05_context_follow_up/first/` 与 `follow-up/` | 未运行 |
| B06 工具失败 | 检索可用，原文读取持续失败；明确错误及不能完成。 | 定向失败后修正示例，通过：错误实际回传，最终 `failed` 并明确“原文读取工具不可用”。 | `test_b06_tool_failure_has_explicit_cause/failure/` | 未运行 |

## 3. 补充检查

每项已在完整离线运行中通过，精确测试 ID、模式及证据映射见 `coverage.json`。内存边界测试使用实际工具/运行器但不另外生成 CLI 包，结果保留在逐项报告中。

| 编号 | 检查 | 实际结果与解释 |
| --- | --- | --- |
| X01 | 信息不足时具体澄清 | 输入“多久？”，`needs_clarification`，明确询问事项/制度，非泛泛“请补充”。 |
| X02 | 调用上限 | 两步后 `incomplete`、`EXECUTION_LIMIT`，明示尚未再次观察的调用；不免费生成最终答案。 |
| X03 | 不存在 ID、错误片段 | D999 和错引 15 天均被拒绝，未进入支持关系接受阶段，最终不是完成。 |
| X04 | 工具失败不能伪报成功 | 失败读取后故意提交完成候选，因无成功读取证据被 `CITATION_INVALID` 拒绝。 |
| X05 | 片段存在与支持答案分开 | 原文完整性通过后，Mock 支持复核拒绝“宠物医疗费可报销”，最终 `incomplete`。不证明真实复核模型能识别此问题。 |
| X06 | 不固定措辞或唯一顺序 | 两条合法顺序、不同完整句子及“三十日”表述均接受；事实、引用、状态仍被检查。 |
| X07 | 不能引用未读取尾部 | 即使文字确实在资料文件中，未读范围的引用也被拒绝。 |
| X08 | 非零偏移 | 从正文中间读取并引用正确连续片段，可正常完成，不误拒合法 Unicode 位置。 |
| X09 | 工具恢复 | 第一次读取失败、第二次读取成功；第二次调用来自新的 Mock 决定，引用只使用成功调用。 |
| X10 | 无动作无限循环 | 持续空动作响应仍消耗额度，3 步后明确未完成。 |
| X11 | 重复调用 ID | 明确协议失败，不覆盖或借用旧读取证据。 |

原有 49 项测试继续执行，覆盖工具隔离、同义词、原文、参数、HTTP 替身协议、错误回传、历史、模式边界、记录与脱敏。新增 17 项离线验收/边界测试后为 66 项实际通过；另有 6 项真实模型测试未执行。

## 4. 失败、定位、修正与重跑

本轮没有把最终成功描述为首次全部通过：

1. 实际定向命令：`python -m tests.run_validation --output-dir examples/checks/acceptance/initial-b06 --test tests.test_acceptance.OfflineAcceptanceTests.test_b06_tool_failure_has_explicit_cause`。退出码 1，1 项失败。
2. 具体原因：Mock 示例返回 `failed` 正确，但说明只写“未取得足够资料，无法完成”，没有明确指出工具不可用；最终说明容易与无相关资料混淆。[原始失败日志](../examples/checks/acceptance/initial-b06/test-output.txt)及[当时实际输出](../examples/checks/acceptance/initial-b06/cases/test_b06_tool_failure_has_explicit_cause/failure/output.json)已保留。
3. 只修改 `tests/fixtures/mock_actions/tool_error.json` 的失败说明、缺口和公开简要依据，保留动作、工具故障与失败状态。没有修改业务分支，也没有声称修复了真实模型能力。
4. 定向重跑同一测试，结果 1 项通过、退出码 0，见[重跑日志](../examples/checks/acceptance/fixed-b06/test-output.txt)。
5. 之后执行完整命令，66 项通过、6 项真实未运行；当前结果及哈希见完整报告。初次失败与定向记录对应其当时版本，完整报告对应当前测试文件。

## 5. 真实模型验证入口与评价规则

已新增 `tests/test_live.py` 的六项真实模型检查，复用结果核对逻辑，但不加载 Mock 动作。默认跳过；只有本机模型配置齐备且显式启用 `--live` 才可联网。

当前只有离线命令实际执行。下面为**未运行的真实验证命令**，需另选尚不存在的目录，并准备本机 `OPENAI_API_KEY/OPENAI_MODEL`：

```powershell
python -m tests.run_validation --live --output-dir examples/checks/acceptance/live-manual-001
```

真实检查关注事实、引用原文及读取证据、最终状态和历史传递，不绑定完整自然语言字符串，不要求唯一检索词、读取顺序或固定调用次数。只有必要的证据存在性会被要求，例如冲突需双方来源，工具失败需实际出现错误。适配器/网络故障将产生失败记录，不替换 Mock 伪报成功。

自动核对仍有限制：期限事实支持阿拉伯数字和常见中文数字，但不是通用语言理解；材料引用和关键词检查不能证明所有自由文本结论均得到支持。真实模型自复核也不是独立事实证明。真实运行后仍需人工检查错误推广、遗漏冲突、额外制度事实及两条路径的决策合理性。**本轮这些真实语义检查、两条真实路径和人工复核均未运行。**

## 6. 复现与未完成项

本轮已运行的完整命令不能原目录重跑，程序拒绝覆盖证据。可换新目录复现离线测试（此目标目录尚未执行）：

```powershell
python -m tests.run_validation --output-dir examples/checks/acceptance/manual-001
```

单独某项可加 `--test`，保存失败后先定位和修复，再用新目录重跑相关检查。`test-report.json` 将通过与 `not_run` 分开，跳过不计为通过。

尚未完成：真实模型验证、真实模型语义效果、原题的两条真实动态路径、资料变更后的真实模型复核、干净环境复现、最终仓库提交。此阶段不创建仓库、不提交或修改权限。测试与执行由 AI 辅助完成，不编造用户个人实现或验证贡献。

## 7. 后续真实执行请求与实际阻碍

用户随后明确要求运行真实模型；此前“先离线验证”的选择不再阻止真实调用。本次未运行成功的原因是当前项目没有取得模型配置，而不是用户未授权。

- 实际检查进程、Windows 用户和系统环境中的 `OPENAI_API_KEY/OPENAI_MODEL`，均不存在；项目也没有 `.env`。只保存存在性，不打印密钥，不擅自搜索无关认证文件。
- 实际执行正常场景的真实模式命令，退出码 1，返回 `MISSING_MODEL_CONFIG`、`mode: real`、`termination_source: initialization`。模型标识为 `null`，API/工具/决策步数均为 0。
- 失败包见 [本次记录说明](../examples/real/attempt-2026-11-01-01/README.md)、[实际输出](../examples/real/attempt-2026-11-01-01/normal/output.json)、[实际初始化 Trace](../examples/real/attempt-2026-11-01-01/normal/trace.jsonl)、[运行配置与命令](../examples/real/attempt-2026-11-01-01/normal/run.json)。
- [状态与验收缺口](../examples/real/attempt-2026-11-01-01/status.json)明确列出 B01—B06 的真实模型检查均为 `not_run`，两条真实路径已取得 0 条。其他场景因共享初始化阻碍未执行，未创建假答案或模型动作。
- 尚未发出 API 请求，因此网络、账号权限和额度也未验证；不能将原因写成这些服务故障。已有 Mock 证据保持原模式，未冒充真实记录。
- 已请求用户提供配置位置/变量名及模型标识，不索取聊天中的密钥。收到可用配置后才能继续真实验证；本轮未改生产代码或重跑离线测试。

## 8. DeepSeek 真实运行、定位与验收（上一阶段）

### 8.1 运行事实

用户随后选择 DeepSeek 并提供临时认证配置。本轮仅接入这一种真实服务，依据 [DeepSeek Responses 官方协议](https://api-docs.deepseek.com/guides/responses_api/)及[工具调用文档](https://api-docs.deepseek.com/guides/tool_calls/)，没有同时保留另一家真实适配器。实际模型 `deepseek-flash`、模式 `real`、`reasoning.effort=none`；每次模型收到全部限量工具观察，结果通过原调用 ID 回传。

日期 2026-11-01（Asia/Shanghai），Python 3.10.0。普通受限进程联网报 Windows 10013，获准联网进程随后实际成功；这是本机网络限制，不能写成密钥无效。认证只经隐藏输入驻留进程，不在命令参数、项目文件或公开证据中。

- 最新离线命令：`python -m tests.run_validation --output-dir examples/checks/deepseek/acceptance-final`，退出码 0；78 项发现中 68 离线通过、10 真实在该批 `not_run`。见[报告](../examples/checks/deepseek/acceptance-final/test-report.json)。
- 真实测试实例累计 12 次：10 通过、2 失败、0 错误；按测试 ID 取最新结果为 10 项通过（B01—B06 加四项补充），不是首次全部通过。
- 保存 14 份真实输入/输出/Trace/元数据/资料快照，67 次实际模型请求，含失败与修正。原始失败完整保留，无 Mock 降级、预填结果或修改 Trace。
- 逐项实际输出、步骤与可复制命令见[真实运行报告](../examples/real/deepseek-2026-11-01/README.md)，机器汇总见 [summary.json](../examples/real/deepseek-2026-11-01/summary.json)，保存证据核验见 [audit.json](../examples/real/deepseek-2026-11-01/audit.json)。

### 8.2 六项业务与补充验收

| 项目 | 实际与结论 | 报告/证据入口 |
| --- | --- | --- |
| B01 明确答案 | 真实重跑通过，原文30天，完成并通过独立支持复核。 | [normal-fixed](../examples/real/deepseek-2026-11-01/normal-fixed/test-report.json) |
| B02 冲突 | 真实通过，检索后读取双方，保留30/15天证据，请求确认，无日期优先推断。 | [冲突输出](../examples/real/deepseek-2026-11-01/business/cases/real/test_b02_conflicting_documents/conflict/output.json) |
| B03 资料外 | 真实通过；即使有报销词项候选仍明确缺少宠物医疗费范围，未完成。 | [资料外输出](../examples/real/deepseek-2026-11-01/business/cases/real/test_b03_outside_corpus_with_partial_keyword_hits/outside/output.json) |
| B04 改写 | 原问与改写独立运行，各4次请求，30天及D01引用一致。 | [business报告](../examples/real/deepseek-2026-11-01/business/test-report.json)（该批B05失败另列） |
| B05 上下文 | 修正首轮过严断言后通过；第二轮传首轮实际问答，重读D03，回答发票和出差审批单。 | [追问输入](../examples/real/deepseek-2026-11-01/follow-up-fixed/cases/real/test_b05_context_follow_up/follow-up/input.json)、[追问输出](../examples/real/deepseek-2026-11-01/follow-up-fixed/cases/real/test_b05_context_follow_up/follow-up/output.json) |
| B06 工具失败 | 真实通过；实际错误回传后模型补查并再读，持续故障后failed，无成功引用。 | [故障Trace](../examples/real/deepseek-2026-11-01/business/cases/real/test_b06_tool_failure_has_explicit_cause/failure/trace.jsonl) |
| 表述不足、上限、无相关 | 均真实通过：具体澄清；1次后incomplete/EXECUTION_LIMIT；零结果后明确资料缺口。 | [补充报告](../examples/real/deepseek-2026-11-01/follow-up-fixed/test-report.json) |
| 资料变更复核 | 仅D02正文15改30，问题/历史/日期/模型/上限不变；读取双方一致原文后completed。资料快照差异已审计。 | [变更输出](../examples/real/deepseek-2026-11-01/follow-up-fixed/cases/real/test_conflict_content_change/same-deadline/output.json) |

不存在ID、错误片段、未读区间、工具失败伪报成功和“片段存在但不支持结论”等确定性边界沿用离线测试，已通过。未安排真实模型故意生成错误引用的对抗实验，不能把这些边界测试说成真实模型实验。

### 8.3 不同路径的具体证据

正常：第2步实际读取D01“报销期限 30 天。”→第3步模型answer→第4步assess_answer支持→completed。[正常Trace](../examples/real/deepseek-2026-11-01/normal-fixed/cases/real/test_b01_clear_answer/normal/trace.jsonl)

冲突：第2步检索实际含30/15天→第3、4步模型分别读D01、D02查证→第5步模型clarify，双方原文保留。该次第1步多动作整批拒绝也完整保留，读取后没有发生额外搜索，不能按示意路径补日志。[冲突Trace](../examples/real/deepseek-2026-11-01/business/cases/real/test_b02_conflicting_documents/conflict/trace.jsonl)

故障：第2步原文读取实际失败→第3步模型再次搜索→第4步模型再次读取仍失败→第5步模型stop/failed。重试是模型的新选择，代码没有自动重试工具。[故障Trace](../examples/real/deepseek-2026-11-01/business/cases/real/test_b06_tool_failure_has_explicit_cause/failure/trace.jsonl)

因此本批至少两条真实路径已取得；不是场景配置控制下一步。Trace观察ID、工具返回和后续动作关联与适配器回传实现共同核对，不把日志自述当唯一闭环证明。

### 8.4 失败与定向修复

1. 首次正常真实测试失败，7次请求；模型猜测 `read_call_id`，引用完整性校验两次拒绝，最后failed。[原始smoke报告](../examples/real/deepseek-2026-11-01/smoke/test-report.json)。原因是协议调用ID对模型文本不够显式。成功读取结果现返回可信句柄，引用错误只反馈真实成功读取的ID与区间；提示要求逐字复制，不放松校验。新增2项回归，相关5项通过，再运行完整离线与正常真实重跑，后者4次请求通过。
2. business批B05首轮失败，原因为测试要求“差旅报销期限”首轮必须completed，然而原文只笼统规定报销30天。模型明确保留适用范围缺口后停止；这应允许作为真实历史，而非强迫补造制度。仅修正测试，首轮仍要求真实D01引用，第二轮仍严格检查材料事实和D03。保存旧失败，离线回归68通过，再真实重跑B05与4项补充，5项通过。
3. DeepSeek可能返回多动作或未知动作。本地拒绝、反馈并计数，模型后续有实际修正；这些事件没有删减。首次smoke为旧源码，其余13包的生产源码哈希与当前一致；测试版本差异分别记录于各批报告。

### 8.5 限制与交付差距

本批逐条语义核对由AI完成：正常30天、冲突双方、材料D03均对应原文；资料外和工具故障没有伪报制度已查明。同模型复核并非独立事实保证，AI核对也不是用户或第三方人工验收。尚未做重复稳定性/大样本测试、干净环境复现或独立人工语义评审。

当前有至少三类完整材料、六项真实业务证据和两条不同路径；最终交付仍缺独立AI使用说明、最终复盘/用户实际用时、真实GitHub URL、完整commit SHA与评审权限核验。本阶段不创建/提交仓库、不编造链接或工时。

本轮适配、代码修正、测试、实际执行及报告由AI辅助完成。用户定义范围、验收与服务配置；协作记录没有用户手工改码或亲自运行测试的证据，不替其编造个人贡献。

## 9. 一个短语映射增量与实际反事实

用户采纳“报销时效 → 报销期限”方案。本轮由AI在 `src/tools.py` 增加一个词条，`tests/test_tools.py` 增加2项回归，`tests/test_live.py` 增加同义问法的2项真实检查入口。没有改动Agent决策循环、提示或引用核验；原始场景文件未改，变更资料在新证据目录独立生成。源码前后副本及单行差异均保存。

- 修改前/后的固定工具输入“报销时效有多久？”：normal资料D01/D03分数由2/2变成6/2，候选区分度提高；冲突双方候选、日期和原文均保留。
- 完整离线实际命令 `python -m tests.run_validation --output-dir examples/improvements/synonym-001/offline`，退出码0；82项发现中70通过、12真实未运行。见[离线报告](../examples/improvements/synonym-001/offline/test-report.json)。
- A0（旧词表，30/15）：真实5次请求，读取双方、请求确认，needs_clarification。
- A1（新词表，同样30/15）：真实5次请求，读取双方并保留冲突，needs_clarification。
- B1（同A1源码，只有D02正文15→30）：真实6次请求，读取两份一致原文，回答30天、引用双方且支持复核通过，completed。

问题均为“报销时效有多久？”，历史为空，模型deepseek-flash、real模式、reasoning none、上限8。三组共16次模型请求，三项检查通过。实际执行顺序是A0→B1→A1（按测试加载顺序），报告按对照关系列出，原始时间未修改。被拒的多动作、工具实际结果、模型后续修正全部保留。

A0/A1比较代码增量，A1/B1隔离资料反事实：输入、运行配置、生产源码相同，只改变D02正文；保存证据检查确认这一差异。三组共6条最终引用经来源、版本、原文片段和成功读取核验。逐项实际回答、动作、查询、引用和状态见[改进报告](../examples/improvements/synonym-001/README.md)、[comparison.json](../examples/improvements/synonym-001/comparison.json)和[audit.json](../examples/improvements/synonym-001/audit.json)。

结论范围：可确认固定查询的工具区分度提高，以及模型对冲突/一致资料作出不同响应。三次模型搜索均自行加入了“期限”；A0/A1调用数相同，不能宣称总体模型质量提高或调用减少。没有在本次词条修改后整批重跑旧十项真实验收，旧记录对应旧工具哈希；全量离线回归与两个新问法的真实检查是不同证据。

[贡献记录](../examples/improvements/synonym-001/contributions.json)明确区分用户提出的要求与选择、AI分析/编码/执行，以及待用户亲自复核。当前没有用户本次手改、亲自运行或完成复核的记录，user_review为pending。独立AI使用说明与最终复盘仍待后续指定阶段，不能将本次方案选择写成个人独立实现或已验收。

### 9.1 用户亲自运行的首次反馈与目录说明修正

用户随后实际执行 `python -m unittest tests.test_tools -v`，粘贴结果为 `ModuleNotFoundError: No module named tests.test_tools`。终端位于个人目录，不是E:/temp2。unittest显示的1项是加载失败占位项，项目的22个工具测试尚未加载，不能记录成“用户测试通过”。用户执行时间、系统退出码未提供，不补造。

上轮AI提供的单独命令漏写切目录步骤；现补充先 `Set-Location -LiteralPath 'E:\temp2'` 再运行。AI在项目目录实际定向执行22项，通过；该结果与用户首次失败分开，不能代替用户亲自重跑。业务源码和测试实现未改。

脱敏后的用户原始反馈与归因见[用户记录](../examples/improvements/synonym-001/review-command-fix/user-attempt-01.json)，AI实际日志见[工具测试日志](../examples/improvements/synonym-001/review-command-fix/ai-tool-tests.txt)。贡献状态更新为user_review=in_progress，用户手工修改尚无记录，修正后用户重跑和反事实材料复核均待确认。
