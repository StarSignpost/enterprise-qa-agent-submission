# 第3题：实际评估、失败与限制

整理日期：2026-11-01（Asia/Shanghai）。本页只采用保存的实际输入、输出、Trace和测试报告；通过数不是效果百分比。没有为了符合预期修改历史日志。本轮文档整理不重新调用真实模型。

## 1. 版本与结论范围

S0为句柄修复前，S1为修复后/词条前，S2为最终词条后。标签不是Git提交，具体源码哈希见各包 `run.json` 和[最终证据索引](../examples/checks/delivery/evidence-index.json)。S1与S2只有 `src/tools.py` 的一个短语映射差异；仍不跨版本自动视为通过。

| 记录 | 实际执行及结果 | 适用范围 |
| --- | --- | --- |
| [S2完整离线](../examples/improvements/synonym-001/offline/test-report.json) | 82项发现：70通过、12真实未运行；退出码0。 | 工具、受控循环、协议替身、Mock六业务及边界；不证明真实模型效果。 |
| [S1完整真实阶段](../examples/real/deepseek-2026-11-01/README.md) | 连同S0初次失败共执行12个测试实例：10通过、2失败；六业务及四补充按ID取最新通过。 | 词条前代码，初次失败和重跑分别保留；不是最终源码全量真实通过。 |
| [A0词条前基线](../examples/improvements/synonym-001/A0-before/test-report.json) | 1项真实通过，5次模型请求。 | S1、新同义问法、冲突资料。 |
| [S2词条后真实](../examples/improvements/synonym-001/after-real/test-report.json) | 2项真实通过，合计11次请求。 | 冲突与一致资料两组，不替代S2其他业务复测。 |
| [AI定向工具复核](../examples/improvements/synonym-001/review-command-fix/ai-run.json) | 在项目目录执行22项工具测试，全部通过。 | 是AI执行，不能写成用户亲自通过。 |
| [用户首次实际运行](../examples/improvements/synonym-001/review-command-fix/user-attempt-01.json) | 在个人目录运行，模块加载失败；项目工具测试执行0项。 | 用户提供的终端反馈，执行时间/系统退出码未知；纠正后重跑待确认。 |
| [本轮Mock命令核对](../examples/checks/delivery/mock-command.json) | completed，4次决策/复核、2次工具、0 API。 | 当前源码CLI入口和证据输出，属于Mock。 |

真实证据共17包、83次记录中的模型请求尝试，跨S0/S1/S2且含失败，**不是17次最终源码通过或83个独立效果样本**。只有2包的全部生产源码哈希与最终源码一致。此前缺配置的初始化失败API为0，未计入真实决策包。

## 2. 六项业务的预期与实际

| 项目 | 预期 | 实际与结论 | 证据 |
| --- | --- | --- | --- |
| 明确答案 | 无冲突且原文30天，读取后回答并引用。 | S1：completed，D01逐字引用，4次请求含支持复核；S2该标准用例未单独真实重跑。 | [输入/输出/Trace](../examples/real/deepseek-2026-11-01/normal-fixed/cases/real/test_b01_clear_answer/normal/) |
| 文档冲突 | D01=30、D02=15，无范围和优先级时查证双方并确认。 | S2 A1：读取双方，说明不能凭日期认定D02优先，needs_clarification。 | [A1实际输出](../examples/improvements/synonym-001/after-real/cases/real/test_conflict_with_synonym_question/conflict/output.json) |
| 资料外 | 宠物医疗费报销范围不在资料中，明确缺口。 | S1：虽部分词项命中，读取后仍incomplete，没有肯定/否定制度结论。S2待复测。 | [实际输出](../examples/real/deepseek-2026-11-01/business/cases/real/test_b03_outside_corpus_with_partial_keyword_hits/outside/output.json) |
| 相似改写 | 标准与改写独立输入，事实/引用一致，不绑定全文或顺序。 | S1两次均completed/30天/D01，各4请求。S2工具词条及同义问法对照另见第4节。 | [两份独立记录](../examples/real/deepseek-2026-11-01/business/cases/real/test_b04_paraphrase_preserves_facts_and_sources/) |
| 上下文 | 追问“那需要什么材料？”从实际历史识别差旅，本轮读取D03。 | S1首轮保留适用范围缺口；第二轮completed，发票/出差审批单，5请求。S2待复测。 | [两轮输入输出](../examples/real/deepseek-2026-11-01/follow-up-fixed/cases/real/test_b05_context_follow_up/) |
| 工具失败 | 读取失败交回模型，由模型决定后续；没有原文不能报完成。 | S1：search→read失败→模型再次search→read失败→stop failed，5请求、无成功引用。S2待复测。 | [故障Trace](../examples/real/deepseek-2026-11-01/business/cases/real/test_b06_tool_failure_has_explicit_cause/failure/trace.jsonl) |

S1的故障终态failed是该验收的正确预期，不是测试失败。需要澄清也不等于已经给出了唯一制度答案。

## 3. 保护机制与分层验证

| 检查 | 实际证据及边界 |
| --- | --- |
| 具体澄清 | S1“多久？”直接clarify，问事项及影响范围的字段，[真实输出](../examples/real/deepseek-2026-11-01/follow-up-fixed/cases/real/test_underspecified_question/ambiguous/output.json)。S2离线仍覆盖。 |
| 达上限明确未完成 | S1上限1后incomplete/EXECUTION_LIMIT，未再次观察调用有记录，[真实包](../examples/real/deepseek-2026-11-01/follow-up-fixed/cases/real/test_execution_limit/limit/)。S2受控测试覆盖空/无效动作也耗预算。 |
| 无相关资料 | S1模型三次自行改写检索均零结果后stop incomplete，[真实包](../examples/real/deepseek-2026-11-01/follow-up-fixed/cases/real/test_no_related_documents/no-match/)。 |
| 假ID、错片段、未读区域 | S2离线X03/X07及单元测试拒绝；不是专门诱导真实模型造假的对抗实验。 |
| 工具失败不能假成功 | S2离线X04明确读取错误后提交answer，完整性核验拒绝；未进入语义复核。 |
| 存在片段不等于支持答案 | S2离线X05：完整性先通过，Mock支持复核拒绝，最终incomplete；机制可验证，Mock结论不证明真实语义裁判质量。 |
| 观察确实回传 | `test_models`检查完整下一HTTP载荷中的历史、原call_id、错误和预算；真实包记录下一请求观察ID及动作。无独立网络抓包。 |
| 模式/异常/重试 | S2确定性测试核对不降级、接口错误、重复ID、预算及日志；真实多动作拒绝和修正保留。 |

70项离线分布为22项工具、26项Agent/CLI、5项协议、17项业务/边界。协议HTTP替身与Mock都是零网络，不混入真实计数。对应逐项名称和结果在完整报告，不要求模型完整措辞或唯一顺序。

## 4. 小改进和反事实

固定工具输入“报销时效有多久？”在normal资料下，D01/D03从2/2变为6/2。工具候选区分度提高，双方冲突候选、版本和原文仍保留。见[修改前](../examples/improvements/synonym-001/before-tools.json)、[修改后](../examples/improvements/synonym-001/after-tools.json)及[单词条差异](../examples/improvements/synonym-001/implementation.patch)。

| 组别 | 对照条件 | 动作、引用、答案和状态 |
| --- | --- | --- |
| A0 | S1，用户问题同下，D01=30/D02=15。 | 检索、读取双方、引用30/15，clarify；5请求。 |
| A1 | S2，问题/历史/资料/服务配置同A0，仅映射新增。 | 仍读取双方、保留引用和冲突，clarify；5请求。 |
| B1 | S2，同问题/历史/配置/源码，仅D02正文15→30。 | 读取双方30天原文，answer后assess_answer支持，completed；6请求。 |

问题均为“报销时效有多久？”，无历史，模型deepseek-flash，reasoning none，上限8。A0/A1比较代码，A1/B1隔离资料。实际测试加载顺序为A0→B1→A1，按对照关系列表不会改变原始日期或日志。

当前两条真实路径可直接核对：

- [A1 Trace](../examples/improvements/synonym-001/after-real/cases/real/test_conflict_with_synonym_question/conflict/trace.jsonl)：第1步search，第2步实际多动作被拒绝，第3/4步read双方，第5步clarify。
- [B1 Trace](../examples/improvements/synonym-001/after-real/cases/real/test_agreement_with_synonym_question/agreement/trace.jsonl)：第1步search，第2步多动作被拒绝，第3/4步read双方，第5步answer，第6步assess_answer，完成。

两份资料差异、同配置、最终引用及源码哈希已审计，见[comparison](../examples/improvements/synonym-001/comparison.json)和[audit](../examples/improvements/synonym-001/audit.json)。三次模型都自行在搜索词中加入“期限”；因此可确认固定查询的词项区分度提高，以及资料变化后的行为响应，**不能证明总体回答质量提升或调用减少**。

## 5. 失败、定位、修正和重跑

| 实际失败 | 定位与改动 | 实际重跑及保留证据 |
| --- | --- | --- |
| 离线Mock工具故障说明过于笼统。 | 终态虽failed，却难以区分没资料与工具坏；只修正Mock脚本说明和缺口，不改业务分支。 | [原失败](../examples/checks/acceptance/initial-b06/test-output.txt)、[定向重跑](../examples/checks/acceptance/fixed-b06/test-output.txt)保留。不能声称提升真实模型能力。 |
| S0正常真实运行失败，7请求。 | 模型猜测读取句柄，两次CITATION_INVALID；原文已取到但标识对模型不够显式。给实际读取数据加入可信read_call_id，错误仅反馈成功读取句柄，保留严格校验。 | [smoke原始记录](../examples/real/deepseek-2026-11-01/smoke/)，新增回归后[S1重跑](../examples/real/deepseek-2026-11-01/normal-fixed/test-report.json)4请求通过。 |
| S1 business批4通过、B05失败。 | 首轮测试强制差旅期限completed，但资料未明确差旅适用范围。没有删缺口或补造制度；改测试允许首轮澄清/未完成，仍要求真实D01引用，追问仍严查D03材料。 | [原失败报告](../examples/real/deepseek-2026-11-01/business/test-report.json)、[定向及补充报告](../examples/real/deepseek-2026-11-01/follow-up-fixed/test-report.json)保留。 |
| 用户命令ModuleNotFoundError。 | 用户在个人目录执行，尚未加载项目工具测试。AI上轮独立命令漏了切目录；补文档，不改源码或测试。 | [脱敏反馈](../examples/improvements/synonym-001/review-command-fix/user-attempt-01.txt)、[AI在根目录22通过](../examples/improvements/synonym-001/review-command-fix/ai-tool-tests.txt)分开；用户纠正后重跑未确认。 |

早期缺模型配置初始化失败的API为0，[记录](../examples/real/attempt-2026-11-01-01/README.md)未冒充真实请求。普通受限进程曾Windows10013，获准联网进程实际取得DeepSeek响应；不能误记为认证失败。一次证据整理进程退出、原因未确认，检查无目标文件后重试成功，见改进审计，未因此改写模型日志。

## 6. 本轮最终文档核对

本轮重新读取最终实现、测试定义、资料、原题必要要求和实际记录；备份旧文档到 [docs-before](../examples/checks/delivery/docs-before/)，整合重复阶段说明，不改旧运行输出/Trace。执行当前源码离线CLI核对命令和五文件，未调用真实模型；完整离线/AI工具报告按哈希复核，没有为文档修改再重复全量测试。

[交付报告](../examples/checks/delivery/report.json)记录必需文件、源码/测试与报告哈希、17包完整性/引用及模式、当前与历史源码差异、文档链接和文本脱敏检查。此类检查是文件/证据核对，不等同业务或人工语义验收。

## 7. 限制与剩余工作

1. S2仅两项真实增量通过，标准正常、资料外、上下文、工具故障等整批真实复测仍缺。
2. 同模型复核可能误判；未做独立人工语义验收、大样本/重复稳定性、真实伪造引用对抗实验。
3. Trace是结构化工程证据，不是所有无效原始回复的完整转储或独立网络抓包。仅本机Python3.10.0/Windows实测；干净环境和其他系统未验证；轻量检索泛化有限。
4. 用户一次真实运行反馈是加载失败；纠正后工具重跑、源码/反事实证据亲自核查未确认。由AI代拟文档不改变执行归属。
5. GitHub URL、最终SHA与评审权限未核验，总开发及个人工时未知；不以运行时段推算三小时或个人贡献。
