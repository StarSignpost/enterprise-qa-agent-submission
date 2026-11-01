# 最终源码六项业务真实验收

日期：2026-11-01（Asia/Shanghai）。本轮由AI按用户“补上吧”的要求执行，使用最终词条后的源码。模式为real，DeepSeek deepseek-flash，reasoning.effort=none；每个CLI轮次最多8次模型请求，候选复核和无效响应计入上限。

实际结果为 **6项检查通过、0失败、0错误、0跳过**，保存8份完整证据包，共41次模型请求。真实输入、输出、Trace、资料快照和命令均来自执行，不修改日志。六项通过不表示所有业务状态都是completed：资料外未完成、工具故障failed均是预期状态。

| 验收 | 实际状态与依据 | API请求 | 五文件证据包 |
| --- | --- | ---: | --- |
| B01 明确答案 | completed；读取D01，回答30天并引用原文，支持复核通过。 | 4 | [normal](cases/real/test_b01_clear_answer/normal/) |
| B02 冲突 | needs_clarification；读取D01/D02，列出30/15双方证据，请求确认，未按日期选一条。 | 5 | [conflict](cases/real/test_b02_conflicting_documents/conflict/) |
| B03 资料外 | incomplete；现有期限/材料条款不能确定宠物医疗费报销范围，列明缺口。 | 6 | [outside](cases/real/test_b03_outside_corpus_with_partial_keyword_hits/outside/) |
| B04 相似改写 | 原问与改写独立运行，均completed，事实30天、D01引用可核验。 | 5 + 4 | [original](cases/real/test_b04_paraphrase_preserves_facts_and_sources/original/)、[paraphrase](cases/real/test_b04_paraphrase_preserves_facts_and_sources/paraphrase/) |
| B05 上下文 | 首轮保留差旅适用范围缺口并澄清；追问携实际历史，重新读D03，回答发票和出差审批单，completed。 | 8 + 4 | [first](cases/real/test_b05_context_follow_up/first/)、[follow-up](cases/real/test_b05_context_follow_up/follow-up/) |
| B06 工具失败 | failed；实际读取错误交回模型，模型补查并再次读取，持续失败后停止，无成功引用。 | 5 | [failure](cases/real/test_b06_tool_failure_has_explicit_cause/failure/) |

B05的上限是每个用户轮次8次，首轮第8次选择合法澄清终态，未在额度外免费总结；第二轮是新的CLI运行。多动作/错误动作及之后的模型修正完整保留，测试不要求唯一顺序或全文措辞。

## 实际命令和配置

项目根目录执行过的命令为：

```powershell
python -m tests.run_private_live --model deepseek-flash --output-dir examples/real/final-six-2026-11-01 --test tests.test_live.LiveAcceptanceTests
```

输出目录已存在，复现需新目录。认证通过隐藏输入进入进程内存，未保存；实际包装命令见[invocation.json](invocation.json)，批次日期、逐项结果和源文件哈希见[test-report.json](test-report.json)，原始测试输出见[test-output.txt](test-output.txt)。

每包含input/output/trace/run/documents。AI核对8包全部生产源码及测试/数据哈希与当前代码一致；10条最终引用通过ID、版本、字符区间、逐字原文及本轮成功读取校验；工具结果关联到下一次模型请求，见[audit.json](audit.json)。该核对不是独立网络抓包或人工语义签署。

最终版本已有本批正常、资料不足、工具失败三类完整材料，及冲突后澄清、原文充分后回答等真实不同路径。此前[同义词反事实](../../improvements/synonym-001/comparison.json)仍有效，只有D02的15→30资料变化，词条后的冲突与一致两包同样匹配最终生产源码。

70项完整离线通过记录另存于[offline](../../improvements/synonym-001/offline/test-report.json)，其中12项真实在该离线批未运行，不与本批混算。本轮没有修改源码或重复离线全量；源码哈希已核对。

未验证：四项LiveBoundaryTests在最终词条下的整批真实重跑、独立人工语义验收、大样本/重复稳定性、干净环境/其他系统。用户个人的纠正后工具重跑、亲自核查及总用时仍未确认；本批编码归属未改变，运行由AI执行。
