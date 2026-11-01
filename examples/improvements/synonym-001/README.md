# 小改进：报销时效短语映射

日期：2026-11-01（Asia/Shanghai）。用户选择“可以，补充一个短语映射”。本轮代码由AI实施，初始验证由AI执行。随后用户实际在个人目录运行工具测试命令，因模块导入失败未加载项目测试；修正后的用户重跑及完整复核待确认。用户手工修改尚无记录。

生产代码仅在 `src/tools.py` 的 `_ALIASES` 增加“报销时效 → 报销期限”。它作用于检索词项，模型仍自主决定工具和最终动作。日期不作为优先级，原文读取保持原始文本。完整改动见 [implementation.patch](implementation.patch)，原始源码与工具测试保存在 [before-source](before-source/)，修改后副本在 [after-source](after-source/)。

## 确定性工具结果

同一 normal 资料、同一输入“报销时效有多久？”，实际分数为：

| 文档 | 修改前 | 修改后 |
| --- | ---: | ---: |
| D01 报销期限 | 2 | 6 |
| D03 差旅报销材料 | 2 | 2 |

原先依赖 ID 打破平局，现在期限文档分数更高。分数是词项相关性，不是制度权威或回答置信度。修改前后各保存四个工具查询，资料、输入一致，包含标准问法和冲突资料；新回归验证冲突双方仍可检索、版本日期保留、读取片段仍逐字来自原文。

实际工具返回见 [before-tools.json](before-tools.json)、[after-tools.json](after-tools.json)。这两份属于 `tools_only`，不是模型 Trace。修改前文件是上一轮的实际基线，没有覆盖。

## 真实模型与资料反事实

三组均为 `real`、`deepseek-flash`、DeepSeek Responses、`reasoning.effort=none`、Python 3.10.0，问题均为“报销时效有多久？”，历史为空，上限 8 次请求。认证仅由隐藏输入进入内存，没有写入证据。每包保存输入、实际输出、实际 Trace、资料快照、运行命令、配置、起止日期和源码哈希。

| 组别 | 唯一对照变化 | 实际动作与结果 | 请求数 | 完整证据 |
| --- | --- | --- | ---: | --- |
| A0 | 修改前词表，D01=30、D02=15 | 检索、读取双方、列出冲突并请求确认，`needs_clarification`。 | 5 | [A0](A0-before/cases/real/test_conflict_with_synonym_question/conflict/) |
| A1 | 相对 A0 只新增映射，资料不变 | 检索、读取双方，明确不能仅凭新日期选择制度，`needs_clarification`。 | 5 | [A1](after-real/cases/real/test_conflict_with_synonym_question/conflict/) |
| B1 | 相对 A1 仅把 D02 正文的15改成30 | 检索、读取双方一致原文，回答30天并引用两份，支持复核通过，`completed`。 | 6 | [B1](after-real/cases/real/test_agreement_with_synonym_question/agreement/) |

A0/A1 比较映射，A1/B1 才是只改变合成资料的反事实。已核对：A0/A1 的八个生产源码文件中仅 `src/tools.py` 哈希不同，逻辑差异为一个词条；A1/B1 生产源码完全相同，资料快照只有 D02.content 不同，输入及配置完全相同。没有给模型配置下一步或最终答案。

三组真实检查均通过，共16次模型请求。测试加载器实际执行顺序是 **A0 → B1 → A1**，表格按对照关系展示；原始日期和日志保留实际顺序。三组均出现过多动作响应，被程序整批拒绝并反馈，之后由模型重新选择，没有删除这些记录，也没有把被拒动作当作已执行工具。

实际搜索词分别为：A0“报销时效 期限”、A1“报销时效 报销期限”、B1“报销 时效 期限 提交 天数”。**三次模型均自行加入了“期限”**。这些样本验证了冲突处理和资料变化响应，不能证明新词条提高了模型总体回答质量；A0/A1都是5次请求，也没有证据表明调用次数减少。可确认的改进是固定工具输入下的检索区分度。

详细对照见 [comparison.json](comparison.json)，保存证据审计见 [audit.json](audit.json)。引用核验覆盖三包共6条最终引用，检查 ID、日期、字符区间、原文和本轮成功读取句柄；工具结果在下一模型请求的观察关联中。AI 也对照资料核对了实际答案与状态；这不是独立人工验收。

## 实际执行

以下命令已运行，输出目录禁止覆盖：

```powershell
python -m tests.run_private_live --model deepseek-flash --output-dir examples/improvements/synonym-001/A0-before --test tests.test_live.LiveSynonymTests.test_conflict_with_synonym_question
python -m tests.run_validation --output-dir examples/improvements/synonym-001/offline
python -m tests.run_private_live --model deepseek-flash --output-dir examples/improvements/synonym-001/after-real --test tests.test_live.LiveSynonymTests
```

真实 [A0报告](A0-before/test-report.json)为1通过，[修改后报告](after-real/test-report.json)为2通过。A0在编辑映射之前执行并保存，现有源码不能直接重现其旧词表；旧源码副本与运行哈希可核对。真实复现需新目录及可用认证，不要求动作顺序或整段措辞相同。

离线 [报告](offline/test-report.json)为 **70通过、12真实未运行**，共发现82项；该批阻止provider联网。12项跳过不能算通过。新增2项工具回归和2项真实对照入口，复用现有工具执行、错误回传和引用审计。没有把离线结果当作真实决策证据。

一次证据整理命令启动后无输出并退出，检查确认未生成目标文件；关闭登录配置后重试成功，启动失败原因未确认。它不是模型/测试失败，没有因此重跑或修改模型 Trace，审计文件保留此执行说明。

## 修改文件与责任记录

- `src/tools.py`：AI增加一个映射词条。
- `tests/test_tools.py`：AI增加2项工具回归。
- `tests/test_live.py`：AI增加同问题的冲突与一致资料检查入口，A0/A1/B1使用同一入口逻辑。
- `README.md`、`docs/01-requirements.md`、`docs/02-solution.md`、`docs/03-evaluation.md`：AI更新当前结果入口，历史运行事实保留。
- 本目录：AI保存前后工具返回、源码快照、差异、三次真实证据、离线报告及贡献/比较记录；原有真实报告与Trace未覆盖。

贡献逐项记录在 [contributions.json](contributions.json)：用户提出范围、证据和复核要求，并选择本方案；方案分析、代码、测试和以上运行由AI完成。用户选择方案不等于用户手工编码或已经复核。

## 留给用户的复核

目前 `user_review: in_progress`。用户已执行过工具测试命令，但运行目录是个人目录，发生模块加载失败；这是实际用户操作，不记作测试通过。上轮AI给出的单独命令遗漏了切换目录步骤。用户提供的输出经目录脱敏后保存在[原始输出](review-command-fix/user-attempt-01.txt)，归因和状态见[结构化记录](review-command-fix/user-attempt-01.json)。

请先切换到项目目录，再运行工具测试；AI已按该目录实际验证22项通过，见[AI日志](review-command-fix/ai-tool-tests.txt)及[元数据](review-command-fix/ai-run.json)。AI这次通过不代替用户重跑：

```powershell
Set-Location -LiteralPath 'E:\temp2'
python -m unittest tests.test_tools -v
```

也可查看单词条[差异](implementation.patch)，并在项目目录单独运行以下两项回归（用户尚未确认执行）：

```powershell
python -m unittest tests.test_tools.ToolTests.test_reimbursement_validity_synonym_prefers_deadline tests.test_tools.ToolTests.test_validity_synonym_keeps_conflicts_and_original_text -v
```

再比较 A1/B1 的 `documents.json`、`output.json` 和 `trace.jsonl`：确认只有D02的15→30变化，冲突时保留双方证据、资料一致时依据原文完成。用户实际检查了哪些文件、运行了哪些命令及结果，待用户提供后再记录，不预填“已确认”。

未验证：用户亲自复核、同义词泛化/大样本质量、重复稳定性、干净环境复现、最终仓库交付。本次词条修改后没有重跑原先十项真实验收；此前报告对应旧工具哈希，不能跨版本宣称新源码全部真实验收通过。


本次目录问题修正仅更新项目README、本报告、贡献/复核状态、评估补记及审计中的用户状态，新增用户失败输出和AI定向验证记录；未修改业务源码、测试实现或已有模型Trace。用户纠正后实际执行结果待收到后补记。

后续交付收尾：最终源码六业务已另批真实复测，6项通过、8包/41请求，见[最终报告](../../real/final-six-2026-11-01/README.md)。本报告先前未验证列表是当时快照，原始Trace及比较数据不改写；四项真实边界未在S2整批重跑。
