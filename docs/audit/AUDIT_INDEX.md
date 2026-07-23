# 工程审计索引

> 当前完整审计入口：[`docs/current_audit_2026-07-23/00_AUDIT_INDEX.md`](../current_audit_2026-07-23/00_AUDIT_INDEX.md)。本目录 00～15 为历史基线，不能单独代表当前完成度。

- 审计时间：2026-07-10 12:30:00 +08:00
- 项目：低速无人车线控底盘生产下线管理平台 v1.0.2
- 审计性质：证据优先的代码、运行、视觉、仿真、安全和部署审计
- 生产就绪结论：**NOT_READY**

## 入口

1. [执行摘要](00_EXECUTIVE_SUMMARY.md)
2. [项目基线](01_PROJECT_BASELINE.md)
3. [UI 还原审计](02_UI_FIDELITY_AUDIT.md)
4. [页面功能审计](03_PAGE_FUNCTION_AUDIT.md)
5. [前端架构审计](04_FRONTEND_ARCHITECTURE_AUDIT.md)
6. [后端 API 审计](05_BACKEND_API_AUDIT.md)
7. [CAN/DBC/协议审计](06_CAN_DBC_PROTOCOL_AUDIT.md)
8. [仿真端到端审计](07_SIMULATION_E2E_AUDIT.md)
9. [EOL 引擎审计](08_EOL_TEST_ENGINE_AUDIT.md)
10. [数据库/日志/报告审计](09_DATABASE_LOG_REPORT_AUDIT.md)
11. [安全审计](10_SECURITY_SAFETY_AUDIT.md)
12. [测试质量审计](11_TEST_QUALITY_AUDIT.md)
13. [性能可靠性审计](12_PERFORMANCE_RELIABILITY_AUDIT.md)
14. [打包部署审计](13_PACKAGING_DEPLOYMENT_AUDIT.md)
15. [问题登记](14_ISSUE_REGISTER.md)
16. [整改计划](15_REMEDIATION_PLAN.md)
17. [审计清单](AUDIT_MANIFEST.md)
18. [机器可读结果](audit_results.json)
19. [CSV 问题单](issue_register.csv)
20. [2026-07-23 桌面端 UI 一致性与显示问题专项审计](16_DESKTOP_UI_CONSISTENCY_AUDIT_2026-07-23.md)
21. [2026-07-23 当前项目完整审计](../current_audit_2026-07-23/00_AUDIT_INDEX.md)

## 判定口径

`REAL` 仅用于实际运行并取得预期业务结果；`PARTIAL` 表示存在真实链路但语义/闭环不完整；`MOCK` 为固定或 fallback 数据；`STUB` 仅返回预留响应；`MISSING` 为缺失；`UNVERIFIED` 为环境无法验证。构建通过、HTTP 200、按钮有 toast 均不单独等于真实实现。
