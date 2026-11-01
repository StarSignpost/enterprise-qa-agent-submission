# 第3题：实际评估、失败与限制

整理日期：2026-11-01（Asia/Shanghai）。本页只采用保存的实际输入、输出、Trace和测试报告；通过数不是效果百分比。没有为了符合预期修改历史日志。此前文档整理未调用真实模型；随后按补齐要求，最终源码六业务实际运行6项通过，详见第8节。

## 1. 版本与结论范围

S0为句柄修复前，S1为修复后/词条前，S2为最终词条后。标签不是Git提交，具体源码哈希见各包 `run.json` 和[最终证据索引](../examples/checks/delivery/evidence-index.json)。S1与S2只有 `src/tools.py` 的一个短语映射差异；仍不跨版本自动视为通过。

| 记录 | 实际执行及结果 | 适用范围 |
| --- | --- | --- |
| [S2完整离线](../examples/improvements/synonym-001/offline/test-report.json) | 82项发现：70通过、12真实未运行；退出码0。 | 工具、受控循环、协议替身、Mock六业务及边界；不证明真实模型效果。 |
| [S1完整真实阶段](../examples/real/deepseek-2026-11-01/README.md) | 连同S0初次失败共执行12个测试实例：10通过、2失败；六业务及四补充按ID取最新通过。 | 词条前代码，初次失败和重跑分别保留；不是最终源码全量真实通过。 |
| [A0词条前基线](../examples/improvements/synonym-001/A0-before/test-report.json) | 1项真实通过，5次模型请求。 | S1、新同义问法、冲突资料。 |
| [S2最终六业务](../examples/real/final-six-2026-11-01/test-report.json) | 6项通过、0失败/错误/跳过；8份CLI证据包、41次请求。 | 最终源码六业务覆盖，源码哈希一致。 |
| [S2词条后真实](../examples/improvements/synonym-001/after-real/test-report.json) | 2项真实通过，合计11次请求。 | 冲突与一致资料两组，不替代S2其他业务复测。 |
| [AI定向工具复核](../examples/improvements/synonym-001/review-command-fix/ai-run.json) | 在项目目录执行22项工具测试，全部通过。 | 是AI执行，不能写成用户亲自通过。 |
| [用户首次实际运行](../examples/improvements/synonym-001/review-command-fix/user-attempt-01.json) | 在个人目录运行，模块加载失败；项目工具测试执行0项。 | 用户提供的终端反馈，执行时间/系统退出码未知；纠正后重跑待确认。 |
| [本轮Mock命令核对](../examples/checks/delivery/mock-command.json) | completed，4次决策/复核、2次工具、0 API。 | 当前源码CLI入口和证据输出，属于Mock。 |

真实证据共25包、124次记录中的模型请求尝试，跨S0/S1/S2且含失败，**不是25次最终源码通过或124个独立效果样本**。其中10包生产源码与最终版本一致：2包词条对照加本次6业务的8包。此前缺配置的初始化失败API为0，未计入真实决策包。

## 2. 六项业务的预期与实际

| 项目 | 预期 | 实际与结论 | 证据 |
| --- | --- | --- | --- |
| 明确答案 | 无冲突且原文30天，读取后回答并引用。 | S2：completed，D01逐字引用，4次请求含支持复核。 | [当前正常](../examples/real/final-six-2026-11-01/cases/real/test_b01_clear_answer/normal/) |
| 文档冲突 | D01=30、D02=15，无范围和优先级时查证双方并确认。 | S2：读取双方，保留30/15和范围/优先级缺口，needs_clarification，5请求。 | [当前冲突](../examples/real/final-six-2026-11-01/cases/real/test_b02_conflicting_documents/conflict/) |
| 资料外 | 宠物医疗费报销范围不在资料中，明确缺口。 | S2：部分词项命中并读取后仍incomplete，没有肯定/否定公司报销范围结论，6请求。 | [当前资料外](../examples/real/final-six-2026-11-01/cases/real/test_b03_outside_corpus_with_partial_keyword_hits/outside/) |
| 相似改写 | 标准与改写独立输入，事实/引用一致，不绑定全文或顺序。 | S2两次均completed/30天/D01，分别5/4请求；被拒候选与修正保留。 | [当前独立记录](../examples/real/final-six-2026-11-01/cases/real/test_b04_paraphrase_preserves_facts_and_sources/) |
| 上下文 | 追问“那需要什么材料？”从实际历史识别差旅，本轮读取D03。 | S2首轮8请求保留范围缺口并澄清；追问携实际历史，4请求completed，材料来自D03。 | [当前两轮](../examples/real/final-six-2026-11-01/cases/real/test_b05_context_follow_up/) |
| 工具失败 | 读取失败交回模型，由模型决定后续；没有原文不能报完成。 | S2：search→read失败→模型再次search→read失败→stop failed，5请求、无成功引用。 | [当前故障Trace](../examples/real/final-six-2026-11-01/cases/real/test_b06_tool_failure_has_explicit_cause/failure/trace.jsonl) |

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

前一轮文档核对重新读取最终实现、测试定义、资料、原题必要要求和实际记录；备份旧文档到 [docs-before](../examples/checks/delivery/docs-before/)，整合重复阶段说明，不改旧运行输出/Trace。执行当前源码离线CLI核对命令和五文件，未调用真实模型；完整离线/AI工具报告按哈希复核，没有为文档修改再重复全量测试。

[交付报告](../examples/checks/delivery/report.json)记录必需文件、源码/测试与报告哈希、25包完整性/引用及模式、当前与历史源码差异、文档链接和文本脱敏检查。此类检查是文件/证据核对，不等同业务或人工语义验收。

## 7. 限制与剩余工作

1. S2六业务整批真实复测6项通过，另有两项词条对照；四项LiveBoundaryTests在S2的整批真实重跑未进行，原真实边界记录仍按S1标注。
2. 同模型复核可能误判；未做独立人工语义验收、大样本/重复稳定性、真实伪造引用对抗实验。
3. Trace是结构化工程证据，不是所有无效原始回复的完整转储或独立网络抓包。仅本机Python3.10.0/Windows实测；干净环境和其他系统未验证；轻量检索泛化有限。
4. 用户一次真实运行反馈是加载失败；纠正后工具重跑、源码/反事实证据亲自核查未确认。
5. 新建公开GitHub仓库已验证无认证页面可读，题号/URL及完整SHA交付方式见SUBMISSION；推送后核对最终HEAD。总开发及个人工时未知，不倒推三小时或个人贡献。

## 8. 最终六业务复测与公开仓库收尾

用户要求补齐并明确“新建仓库，公开”。AI使用最终源码执行LiveAcceptanceTests，实际6项通过、0失败、0错误、0跳过；8包共41次模型请求，10条最终引用的原文/来源/读取句柄核对通过，源/测试/资料哈希与当前一致。见[完整报告](../examples/real/final-six-2026-11-01/README.md)及[审计](../examples/real/final-six-2026-11-01/audit.json)。

本次没有改代码、提高预算、放松断言或反复重跑至成功。原问的含缺口候选被拒后模型自行修正；上下文首轮支持复核不足后继续查证，最终第8次选择澄清。原始事件全部保留，六项通过不等于资料外/故障都返回completed。

新建仓库StarSignpost/enterprise-qa-agent-submission按用户要求公开，无认证网页HTTP200验证可读。匿名GitHub API读取曾受共享限流HTTP403影响，改用无认证网页核对，没有误报认证无效或重复请求限流接口，见[实际记录](../examples/checks/submission/github-public.json)。Git提交/推送由AI代执行，最终完整HEAD在交付回复提供；提交账号不等同于个人手写代码。
