# 当前项目完整审计索引（2026-07-23）

项目：低速无人车线控底盘生产下线管理平台<br>
审计基线：Git `ba47b0aaebc62eae3131d23ed9d318fdb4721130` 加当前未提交工作树<br>
审计边界：静态代码/配置/文档审查、临时目录、Mock 和 `127.0.0.1` 回环；未连接真实 CAN、车辆、USR-CAN115、打印机或非回环地址。

## 一句话结论

当前项目已经是一个功能较完整、Mock/回环验证充分的工程化桌面产品原型，**可用于开发、演示、自动化回归和内部 unsigned 安装包验证；不可直接接入可运动真实车辆并作为生产系统投用**。

量化结论采用三个相互独立的口径：

| 口径 | 估算 | 判定 |
|---|---:|---|
| 软件功能完成度 | 89% | 主要业务闭环已实现，仍有生产配置权威、审计原子性、追溯元数据和运维缺口 |
| 生产部署就绪度 | 52% | unsigned、当前工作树未形成可追溯发行包、现场配置/打印/长期运行未验收 |
| 真实车辆安全就绪度 | 28% | 软件 fail-closed 边界较好，但物理急停、安全 PLC、看门狗、safe-stop 硬件行为均未验证 |

这些百分比是基于代码、测试和证据的工程估算，不是功能安全认证、法规合规结论或量产放行签字。

## 最高优先级结论

1. `production` 仍可调用普通 `PUT /config/channels` 修改通道并写 `channels.yaml`，绕过签名配置包的单一权威路径，应作为 P0 关闭。
2. `record_operator_action()` 吞掉数据库异常；控制动作可能已执行而审计未持久化，应建立发送前审计意图、发送结果和落库失败的原子/补偿策略。
3. `safe_stop.hardware_validated=false` 会安全地阻止 production 普通运动控制，但签名生产配置 schema 又没有受控启用该验收状态的字段；项目当前不存在经过批准的真实车辆运动放行路径。
4. 一键检测创建请求仍带演示底盘号/VIN/序列号默认值，缺少扫码/工单绑定与格式/唯一性约束，不满足量产追溯。
5. CAN 监控后端和前端都存在硬编码 `source_session=S20260401-001` 的路径；系统设置还显示固定配置版本、计划版本、Node 版本、当前时间伪装构建时间，以及 DBC 未加载时的固定报文/信号数量。
6. TCP CAN transport 没有生产级断线重连、退避、半开检测和状态机；若现场选 TCP，目前不应上线。
7. 当前 UI 收口代码未提交，最近远程 Windows CI 验证的是较早提交；现有安装包也是更早 dirty 基线的 unsigned 内测包，不能作为本次当前版本发布证据。

## 文档清单

- [01_FULL_PROJECT_AUDIT.md](./01_FULL_PROJECT_AUDIT.md)：范围、架构、完整性、关键实现与总评。
- [02_MODULE_AND_FUNCTION_COMPLETION.md](./02_MODULE_AND_FUNCTION_COMPLETION.md)：逐模块、逐功能完成度及证据。
- [03_DESKTOP_UI_PAGE_FUNCTION_AUDIT.md](./03_DESKTOP_UI_PAGE_FUNCTION_AUDIT.md)：11 页控件到持久化/审计的追踪与页面评分。
- [04_REAL_ENVIRONMENT_READINESS.md](./04_REAL_ENVIRONMENT_READINESS.md)：真实环境能否运行、分阶段门禁及硬件确认项。
- [05_SECURITY_DATA_DEPLOYMENT_FINDINGS.md](./05_SECURITY_DATA_DEPLOYMENT_FINDINGS.md)：安全、身份、配置、数据、报告、安装和供应链发现。
- [06_TEST_AND_EVIDENCE.md](./06_TEST_AND_EVIDENCE.md)：本轮命令、结果、覆盖率、证据边界和缺口。
- [07_REMEDIATION_BACKLOG.md](./07_REMEDIATION_BACKLOG.md)：P0/P1/P2 后续工作、顺序、验收标准和建议。
- [08_FOLLOWUP_IMPLEMENTATION_PROMPT.md](./08_FOLLOWUP_IMPLEMENTATION_PROMPT.md)：可直接交给后续 Codex/开发团队的完整实施 Prompt。
- [09_AUDIT_BASELINE_AND_METHOD.md](./09_AUDIT_BASELINE_AND_METHOD.md)：已遍历资料、审计方法、工作树状态和结论限制。

## 推荐阅读顺序

产品/项目负责人先读 01、04、07；研发负责人读 02、05、06；桌面 UI 负责人读 03；下一轮实施直接使用 08。
