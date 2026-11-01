# 企业知识问答 Agent · 第 3 题

Python CLI 根据本地合成制度回答问题。真实模型选择检索、读取、澄清、回答或停止；程序执行工具，把实际结果交回模型，再由模型决定下一步。答案包含引用原文、资料缺口与任务状态。

**最终源码六项业务真实检查全部通过：8份运行包、41次模型请求。** 另有70项离线通过及2组词条真实对照。四项真实边界未在最终词条下整批重跑；没有统计总体正确率或稳定性。

## 评审入口

| 内容 | 入口 |
| --- | --- |
| 要求、输入、失败判据与证据映射 | [01-requirements](docs/01-requirements.md) |
| 动态决策、模型/工程边界及取舍 | [02-solution](docs/02-solution.md) |
| 预期、实际、失败、版本与限制 | [03-evaluation](docs/03-evaluation.md) |
| AI与用户的实际贡献、执行及待确认项 | [04-ai-usage](docs/04-ai-usage.md) |
| 工程问题、解决过程、学习结论与用时 | [05-retrospective](docs/05-retrospective.md) |
| 最终词条改进、前后与反事实证据 | [改进报告](examples/improvements/synonym-001/README.md) |
| 最终六项业务真实结果 | [final-six报告](examples/real/final-six-2026-11-01/README.md) |
| GitHub与提交信息 | [公开仓库](https://github.com/StarSignpost/enterprise-qa-agent-submission)、[SUBMISSION](SUBMISSION.md) |
| 本轮文件、证据与脱敏核对 | [交付核对报告](examples/checks/delivery/report.json) |

## 环境、版本和安装

| 项目 | 实际配置或职责 |
| --- | --- |
| Python | 要求3.10+；实际验证3.10.0。其他Python版本、其他操作系统未实测。 |
| 本机运行环境 | Windows、PowerShell；项目目录为 `E:\temp2`。复制到别处后替换目录。 |
| 第三方依赖 | 无；[requirements.txt](requirements.txt)只含说明，无需安装pip包。 |
| Agent框架、模型SDK | 均未使用，版本不适用。循环、状态、保护和协议由 `src/` 实现。 |
| 标准库 | `urllib.request`负责HTTPS，`json`负责协议与资料，`argparse`负责CLI，`unittest`负责测试；版本随Python。 |
| 真实模型 | DeepSeek `deepseek-flash`；日志只记录服务返回的模型标识，未记录底层权重版本。 |

安装Python并取得项目文件后，**先进入项目根目录**。以下命令使用本工作区路径：

```powershell
Set-Location -LiteralPath 'E:\temp2'
python --version
python -m unittest tests.test_tools -v
```

最后一条已由AI在项目目录实际执行，22项通过，见[日志](examples/improvements/synonym-001/review-command-fix/ai-tool-tests.txt)。用户曾在个人目录执行同一测试命令而发生模块加载失败；修正后的用户重跑尚未确认，见[用户实际记录](examples/improvements/synonym-001/review-command-fix/user-attempt-01.json)。

## 离线运行与测试

以下可复制示例使用时间后缀生成新目录，避免覆盖证据；**这些带时间后缀的新命令未实际运行**。已执行的具体命令在各证据包的 `run.json` 或报告中。

```powershell
Set-Location -LiteralPath 'E:\temp2'
$qaOutput = 'examples/review/mock-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
python -m src.cli --mode mock --mock-script tests/fixtures/mock_actions/normal.json --data data/scenarios/normal.json --input examples/inputs/normal.json --max-steps 8 --output-dir $qaOutput
```

本轮实际执行同参数离线CLI，结果为 `mock / completed`、4次决策/复核、2次工具、0次API请求，见[实际输出](examples/checks/delivery/mock-smoke/output.json)及[执行命令](examples/checks/delivery/mock-command.json)。Mock动作和支持复核结论来自脚本，只证明流程，不是模型自主判断证据。

```powershell
Set-Location -LiteralPath 'E:\temp2'
$qaTests = 'examples/review/offline-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
python -m tests.run_validation --output-dir $qaTests
```

已执行的完整离线报告为 [synonym-001/offline](examples/improvements/synonym-001/offline/test-report.json)：发现82项，70通过、12真实测试未运行。运行器在离线模式阻止provider联网，未运行不计为通过。普通 `python -m unittest discover -s tests -v` 不保存完整报告，推荐使用上述运行器。

## 真实运行

只接入DeepSeek Responses，端点 `https://api.deepseek.com/responses`。实现依据 [Responses协议](https://api-docs.deepseek.com/guides/responses_api/)和[工具调用协议](https://api-docs.deepseek.com/guides/tool_calls/)。本次参数为 `reasoning.effort=none`、`max_output_tokens=3000`，每次请求超时30秒，无隐藏HTTP重试。

真实验收入口会隐藏输入认证，恢复原进程环境；以下新目录示例未运行：

```powershell
Set-Location -LiteralPath 'E:\temp2'
$qaLive = 'examples/review/real-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
python -m tests.run_private_live --model deepseek-flash --output-dir $qaLive
```

默认选择六项业务验收。可追加 `--test tests.test_live.LiveSynonymTests` 单独运行两项同义问法对照；要选择多个类，重复 `--test` 并显式列出各类，不能假设默认六项仍会自动追加。另有 `tests.test_live.LiveBoundaryTests` 四项边界。真实请求需要有效认证、可用额度及网络；此前文档整理没有调用真实模型；随后按补齐要求实跑最终六业务，6项通过。

单轮真实CLI需要进程变量 `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`。可在新PowerShell终端用隐藏输入临时配置，以下示例未执行：

```powershell
Set-Location -LiteralPath 'E:\temp2'
$qaKey = Read-Host 'DeepSeek API key' -AsSecureString
try {
    $env:DEEPSEEK_API_KEY = [System.Net.NetworkCredential]::new('', $qaKey).Password
    $env:DEEPSEEK_MODEL = 'deepseek-flash'
    $qaReal = 'examples/review/real-cli-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
    python -m src.cli --mode real --data data/scenarios/normal.json --input examples/inputs/normal.json --max-steps 8 --output-dir $qaReal
} finally {
    Remove-Item Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
    $qaKey = $null
}
```

[.env.example](.env.example)的密钥留空，模型标识公开；程序不自动加载 `.env`。不要把认证值放入代码、命令参数、日志或提交。真实配置/服务失败保持 `real / failed`，不静默换Mock。历史认证成功不代表临时认证现在仍有效。

## 输入、输出和状态

输入JSON为非空 `question` 和可选 `history`（有序user/assistant文本）；历史最多20条，问题加历史最多20,000字符。单次CLI处理一个用户轮次；追问传入前轮实际问答，事实仍须本轮重新取证。

每包保存 `input.json`、`output.json`、`trace.jsonl`、`run.json`、`documents.json`。输出含 `answer/citations/gaps/status`，另含模式、模型、计数、终止来源与核验。引用包含ID、版本、逐字片段、Unicode起止位置和成功读取句柄。终端JSON可能显示Unicode转义，文件为UTF-8。

| 状态 | 含义 | CLI退出码 |
| --- | --- | ---: |
| `completed` | 引用完整性和同模型支持复核均接受候选答案 | 0 |
| `needs_clarification` | 需要具体补充或制度确认，本轮结束 | 0 |
| `incomplete` | 资料不足或额度触顶，明确未完成 | 2 |
| `failed` | 工具、初始化、接口或协议故障导致失败 | 1 |

退出码0包含“需澄清”，不能当作已回答。默认上限8次，所有模型尝试、无效响应和语义复核共用额度；触顶不再免费生成总结。目录存在时拒绝覆盖。

## 完成范围与限制

当前具备CLI、5份隔离合成资料、两工具、唯一真实适配器、独立Mock、历史、预算、参数/错误处理、引用检查及Trace。最终词条把固定工具查询的D01/D03分数从2/2改为6/2；冲突/一致两路径及最终六业务真实复测都有证据。资料外incomplete、工具故障failed属于正确预期，不能把六项检查通过写成八个任务都已回答。

检索只是少量短语与中文双字匹配，可能漏召回/误召回；分数和新日期不是权威。同模型语义复核可能误判，片段存在不能保证支持结论。没有大样本效果、重复稳定性、独立人工语义验收、干净环境或其他操作系统验证；不宣称生产可用。

题号为3，按用户选择新建[公开GitHub仓库](https://github.com/StarSignpost/enterprise-qa-agent-submission)，已核对无认证页面可读。分支main，完整commit SHA在本次交付回复给出，可用git rev-parse HEAD核验，见[SUBMISSION](SUBMISSION.md)。提交与推送由AI代执行，使用公开账号及noreply邮箱。原始卷面含个人信息/专属链接，按 `.gitignore` 排除；仅提交必要合成资料。实际个人用时、会话外贡献和个人学习收获由用户补充，参见AI使用与复盘文档。
