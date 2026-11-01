# 真实模式执行尝试：配置阻碍

本目录是实际执行失败记录，**不是成功的真实模型问答证据**，不能计入真实动态决策路径。

- 日期：2026-11-01，Asia/Shanghai；具体开始/结束时间见 `normal/run.json`。
- 选定模式：`real`。模型标识：未取得（`null`），不猜测模型名。
- 实际退出码：1；错误：`MISSING_MODEL_CONFIG`；终止阶段：初始化。
- API 请求、工具执行、模型决策步数均为 0；未检测网络、权限或额度。
- 未切换 Mock，未新增预设决策或修改旧日志。

实际执行：

```powershell
python -m src.cli --mode real --data data/scenarios/normal.json --input examples/inputs/normal.json --max-steps 8 --output-dir examples/real/attempt-2026-11-01-01/normal
```

`normal/` 保存实际输入、实际失败输出、初始化 Trace、运行元数据与合成资料快照。Trace 只有初始化开始/失败结束，没有模型动作；这符合实际发生的情况。

`environment-check.json` 只记录命名变量在进程、Windows 用户、系统环境中是否存在，以及项目是否有 `.env`，不含密钥。此次均未发现项目要求的 `OPENAI_API_KEY/OPENAI_MODEL`，项目也无 `.env`。这不表示用户在其它终端或配置位置没有配置，而是当前项目无法取得所需配置。

`status.json` 列出六项业务验收及两条路径缺口：B01—B06 均未执行真实模型验证，已观察到的真实动态路径为 0，要求至少 2 条。正常命令已执行但未进入模型阶段；其他场景因相同初始化阻碍未运行，未重复制造多份同类失败记录。

继续所需信息：配置所在文件路径或变量名，以及模型标识。密钥保留在本机，不发送到聊天、不提交仓库。取得配置后使用新的运行目录，保留本次记录。
