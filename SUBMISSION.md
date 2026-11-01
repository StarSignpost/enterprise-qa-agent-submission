# 第3题交付信息

- 题目：企业知识问答Agent（第3题）。
- GitHub仓库：[StarSignpost/enterprise-qa-agent-submission](https://github.com/StarSignpost/enterprise-qa-agent-submission)。
- 可见性：按用户选择设为公开；无认证页面已验证可读；交付时核对main及完整提交SHA，实际结果在交付回复提供。
- 提交分支：main。最终完整commit SHA在本次交付回复中提供；克隆后可用 `git rev-parse HEAD` 核对。
- 评审入口：[README](README.md)、[需求与验收](docs/01-requirements.md)、[最终六项真实报告](examples/real/final-six-2026-11-01/README.md)。

最终源码六项业务真实检查6通过、0失败，共8个CLI运行包、41次模型请求。完整离线70通过，12真实在该离线批未运行；另有词条前后及资料反事实证据。所有模式、版本和失败记录分开，未生成总体通过率。

实现、测试、实际运行和本次Git提交/推送由AI协助完成；用户选择范围、改进方案及新建公开仓库。提交身份使用公开GitHub登录名和noreply邮箱，不表示用户亲手编写或执行了这些代码。AI使用和个人实际反馈见[04-ai-usage](docs/04-ai-usage.md)。

原始卷面、个人信息、真实认证和私有环境不提交。`.gitattributes`只关闭换行转换，保持保存证据的字节哈希，便于跨Git检出核对；运行源码没有为提交而改动。

限制保留在[评估](docs/03-evaluation.md)和[复盘](docs/05-retrospective.md)：独立人工语义确认、稳定性/大样本、干净环境及个人总用时未验证或未知，不虚报完成。
