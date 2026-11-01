# 第3题：需求与验收映射

核对日期：2026-11-01（Asia/Shanghai）。依据用户提供的本地原题“试卷说明”“GitHub交付规范”和第3题；不复制卷面个人信息、专属链接或令牌。

## 1. 用户、目标与要求层级

帮助员工根据制度或产品资料找到可靠答案。输入为问题、可选对话历史和带文档ID/版本日期的合成资料；输出为回答、引用ID及原文片段、资料缺口与任务状态。模型根据实际工具观察选择后续动作。

| 标记 | 含义 | 本项目实例 |
| --- | --- | --- |
| H | 原题硬性要求 | 两个工具、真实模型循环、六业务验收、两路径、执行上限、三类验证材料、完整仓库交付。 |
| U | 用户协作约束 | 中文、按阶段推进、真实/Mock分开、引用完整性与语义支持分开、保留失败、如实记录贡献。 |
| D | 设计选择 | Python/CLI/JSON、单一DeepSeek服务、8次默认预算、四种状态、同模型支持复核、JSONL、具体日期/ID/测试断言。 |

原题允许CLI/HTTP API/Notebook任选，框架可自选；本项目选择CLI和原生标准库。原题建议约3小时、核心优先，并要求记录实际用时；不是已实测达到的工时或虚构的完成率。界面、部署、多Agent和生产Runtime不在核心范围。

## 2. 证据版本与成功标准

以下S0/S1/S2仅为本文的源码阶段标签，不是Git提交：

- **S0**：首次DeepSeek正常运行，引用句柄问题未修复，真实失败。
- **S1**：句柄修复后、增加“报销时效”词条之前。六业务及四补充按测试ID取最新结果通过；旧失败保留。
- **S2**：最终源码，增加一个短语映射。70项离线通过、12项真实在该离线批未运行；真实增量两项通过。旧六业务未在S2整批重跑。

以 `run.json.source_sha256` 为准：[最终证据索引](../examples/checks/delivery/evidence-index.json)逐包列出和最终源码的差异。S1与S2的生产代码只差 `src/tools.py` 的一个映射；仍不能把历史结果自动提升为S2全覆盖。

## 3. 六项业务矩阵

每个下列真实目录均含 `input.json/output.json/trace.jsonl/run.json/documents.json`。表中结论限定于已运行样本，不是普遍效果保证。

| 要求 | 输入 | 预期行为 | 失败判据 | 验证方式 | 实际证据与状态 |
| --- | --- | --- | --- | --- | --- |
| B01 明确答案 H | “报销期限多久？”；D01原文“报销期限 30 天。”，无冲突。 | 模型检索、读取、依据原文回答30天，引用可核验，状态合理。 | 无原文完成、数字不符、假引用、补造制度细节。 | 真实事实/引用/状态核对，检查读取进入下一请求。 | [S1正常](../examples/real/deepseek-2026-11-01/normal-fixed/cases/real/test_b01_clear_answer/normal/)：completed，4请求；S2整项真实待重跑。 |
| B02 冲突 H | D01=30、D02=15；后者日期更新，但没有范围或优先级。 | 查证双方原文，列冲突与缺口并请求确认。 | 单凭日期选15，隐瞒另一份，编造优先级，未解决却完成。 | 核对双方证据与观察后的模型动作；另做只改资料的对照。 | [S2冲突A1](../examples/improvements/synonym-001/after-real/cases/real/test_conflict_with_synonym_question/conflict/)：needs_clarification；[S2一致B1](../examples/improvements/synonym-001/after-real/cases/real/test_agreement_with_synonym_question/agreement/)只改D02为30后completed。 |
| B03 资料外 H | “公司是否报销宠物医疗费？”；只有期限、差旅材料。 | 观察部分匹配仍确认缺少报销范围，不把常识写成公司制度。 | 编造可报/不可报，用期限证明费用范围，故障伪装无资料。 | 真实核对事实与缺口，零结果另测。 | [S1资料外](../examples/real/deepseek-2026-11-01/business/cases/real/test_b03_outside_corpus_with_partial_keyword_hits/outside/)：incomplete；[零结果](../examples/real/deepseek-2026-11-01/follow-up-fixed/cases/real/test_no_related_documents/no-match/)亦incomplete；S2整项真实待重跑。 |
| B04 相似改写 H | 同资料独立问标准问法与“费用报销最迟得在多少天内办？”。 | 事实、引用一致，允许不同检索词/顺序。 | 只识别固定句式、改写后无依据答复或预设答案。 | 独立真实运行，不比较全文或强制唯一顺序；补充固定查询工具检查。 | [S1原问/改写](../examples/real/deepseek-2026-11-01/business/cases/real/test_b04_paraphrase_preserves_facts_and_sources/)均completed；[S2词条改进](../examples/improvements/synonym-001/README.md)有工具与新问法真实证据，未替代完整正常改写复测。 |
| B05 上下文 H | 首问“差旅报销期限多久？”，追问“那需要什么材料？”，携首轮实际历史；D03规定发票及出差审批单。 | 根据历史解析差旅指代，本轮重新读取D03并回答材料。首问可如实保留范围缺口。 | 忽略指代、复述期限、历史当原文、写死特定追问。 | 两轮实际历史/输出/Trace及D03引用核对。 | [S1两轮](../examples/real/deepseek-2026-11-01/follow-up-fixed/cases/real/test_b05_context_follow_up/)：首轮澄清、追问completed；S2真实待重跑。 |
| B06 工具失败 H | 检索可用，读取原文持续返回明确错误。 | 模型观察错误后选补查、重试或停止；无证据不报完成。 | 错误伪装为空/成功、未回传、固定重试冒充决策、无限循环。 | 实际工具故障注入及之后的模型动作；确定性反例补充。 | [S1故障](../examples/real/deepseek-2026-11-01/business/cases/real/test_b06_tool_failure_has_explicit_cause/failure/)：两次实际读取失败，模型最终failed，无成功引用；S2真实待重跑。 |

## 4. 通用要求矩阵

| 要求 | 输入 | 预期行为 | 失败判据 | 验证方式 | 实际证据/缺口 |
| --- | --- | --- | --- | --- | --- |
| G01 真实循环 H | 问题、工具定义、实际观察、剩余额度。 | 模型选择→代码执行→结果交回模型→模型再选择。 | 固定分支、一次生成或只写日志未回传。 | 读 `Agent._observe`、适配器下一载荷及协议单测，对照Trace。 | [方案闭环](02-solution.md)、[S2真实两路径](../examples/improvements/synonym-001/after-real/)已运行。 |
| G02 至少两路径 H | 同问，30/15与30/30资料。 | 不同实际结果导致不同后续动作。 | Mock充当真实、日志补填、只换目录。 | 比较实际读取、后续动作、简要依据和终态。 | S2 A1读双方后clarify；B1读双方后answer/assess_answer。 |
| G03 执行上限 H，计数D | 可配置上限，失败/无效请求。 | 所有模型尝试含复核均计数，触顶明确未完成。 | 免费总结、无效动作不计、无限循环。 | 离线保护及低额度真实。 | [S1真实上限1](../examples/real/deepseek-2026-11-01/follow-up-fixed/cases/real/test_execution_limit/limit/)；[S2离线](../examples/improvements/synonym-001/offline/test-report.json)。 |
| G04 Mock边界 H/U | 两种显式模式及接口故障。 | 模式清楚，真实失败不降级，Mock仅验证流程。 | 静默替换、Mock结论称模型效果。 | 模式与传输替身/错误测试、元数据。 | [当前Mock命令](../examples/checks/delivery/mock-command.json)、真实包及离线报告分开。 |
| G05 可复制运行 H/U | Python、根目录、资料、进程配置。 | 环境/安装/入口/变量/退出码齐备。 | 缺工作目录、未执行称通过。 | 实际本机命令与新目录复现说明。 | [README](../README.md)、[用户目录失败](../examples/improvements/synonym-001/review-command-fix/user-attempt-01.json)已如实记录；干净环境未验证。 |
| G06 三类完整材料 H | 正常、资料不足、工具失败，共同覆盖六业务。 | 至少三组真实输入/输出/运行记录。 | 只有预期、缺场景、复制改名、版本混用。 | 检查五文件完整性，映射B01—B06。 | 历史完整组与增量共17包，含失败，见[索引](../examples/checks/delivery/evidence-index.json)；S2三类全量覆盖仍缺复测。 |
| G07 Trace H | 模型动作、工具参数/观察及后续决定。 | 关联步骤、实际返回摘要、后续动作和公开简要依据。 | 预填日志、缺关联、内部思维或秘密泄露。 | 对照事件及调用ID；非独立网络抓包。 | 逐包trace.jsonl；完整结果与摘要并存，多动作拒绝亦保留。 |
| G08 引用/输出 H/U | 真实读取、候选回答及错误引用。 | 分开检查ID/版本/逐字片段和语义支持，缺口状态如实。 | 假ID、错片段、存在但不支持，失败假成功。 | 代码完整性、单独模型支持复核、离线对抗和AI样本核对。 | [S2离线](../examples/improvements/synonym-001/offline/)、[引用失败原始证据](../examples/real/deepseek-2026-11-01/smoke/)；语义复核仍可误判。 |
| G09 完整交付 H | 代码、五文档、依赖、资料、证据、仓库。 | 材料一致，真实URL/完整SHA及评审访问可核对。 | 缺文件、假链接/SHA、未知权限称已验。 | [交付核对](../examples/checks/delivery/report.json)。 | 文件已补齐；GitHub URL/SHA/评审权限未完成，本阶段不提交。 |
| G10 AI/个人真实性 H/U | 选择、代码、实际命令、结果和用时。 | 按来源和实际行为记录，未知留待补。 | AI写成个人独立完成、失败写通过、编造工时。 | 会话与贡献记录/日志对应。 | [AI使用](04-ai-usage.md)、[复盘](05-retrospective.md)；用户纠正后重跑与总用时待补。 |
| G11 脱敏及范围 H/U | 原题、配置、拟交付材料。 | 排除原题个人信息/秘密，保留失败，按指定阶段推进。 | 密钥/卷面进入提交或擅自发布。 | 忽略规则、文本扫描、文件核对。 | 本轮仅文档与核对材料；原题留本机并排除，最终提交还须核对。 |

## 5. 用户补充边界

“多久？”应具体追问事项；不存在引用、错误片段、未读区间不能完成；失败读取不能伪报成功。这些在当前确定性测试中通过。语义复核不是字符串检查，且同模型复核不是独立事实保证。真实验证检查事实、引用和状态，不要求逐字措辞或唯一顺序。

## 6. 交付与未完成项

当前核对 `src/`、`tests/`、必要 `data/`、`examples/`、README、本文及02—05、requirements.txt与.env.example。详细文件、哈希和证据范围见交付核对报告。题号3已明确；Git仓库、最终URL/完整SHA和评审权限尚未产生或核验。个人实际用时、会话外贡献与个人学习收获由用户据实补充，不影响本轮先完成可核对的文档。
