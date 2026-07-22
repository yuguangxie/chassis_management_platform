# 11 个桌面页面功能追踪矩阵

审计日期：2026-07-22（Asia/Shanghai）  
基线：`docs/current_audit_2026-07-20/02_DESKTOP_UI_PAGE_FUNCTION_AUDIT.md`  
动态边界：仅 Mock 与 `127.0.0.1`，未打开真实 CAN，未向非回环地址发送。

## 结论

11 个业务页面均已建立 `控件 → store/页面状态 → API → backend service → persistence/audit → error state` 链路。所有页面统一使用 `PageDataState` 表达 `loading / empty / error / stale / permission-denied`；权限来自后端 `/auth/me` 返回的 principal，Router 元数据和后端 RBAC 同时生效。前端隐藏写按钮只是体验层，不能替代后端 401/403。

| 页面 | 主要控件 | store / 页面状态 | API | backend service | persistence / audit | 失败、空与 stale |
|---|---|---|---|---|---|---|
| 总览 | KPI、快捷入口、报告扫描、最近会话 | 页面 `loadSummary`、`useAuthStore` | `GET /overview/summary`；`POST /reports/scan`；安全停车独立 API | overview 聚合、`ReportService`、`SafeStopService` | SQLite 会话/报告；报告扫描和安全操作审计 | 网络失败显式 fallback；CAN 离线时 FPS/最后报文显示 `—（stale）`，曲线清空 |
| Network | 通道参数、端口诊断、设备 endpoint、自检、应用/恢复 | 页面原子快照 `config/appliedConfig`、principal | `GET/PUT /config/channels`；`POST /can/channels/self-test`；connect/stop/restore | `CanGatewayManager`、配置 schema、OS socket 诊断 | 配置文件/配置历史/操作审计；应用失败恢复旧 manager 和旧配置 | apply 失败 UI 与后端双重回滚；ping 未测量为 `null`，不显示伪 `0.0 ms`；离线图表清空 |
| CAN 监控 | 筛选、排序、暂停、清空、导出、历史文件 | `useCanStore` | `/can/frames/latest`、decoded、statistics；clear/export/load/delete | `CanGatewayManager`、`DbcService`、原始日志服务 | raw CAN 文件、导出文件、SQLite 删除记录、操作审计 | 网络失败为显式 Mock/stale；离线 RX/TX FPS 显示 `—（stale）`；未实现详情页签禁用 |
| 信号仪表盘 | 实时信号、关注列表、布局、快照 | `useSignalsStore`、`useAuthStore` | `/signals/dashboard`、watchlist、snapshot、dashboard-layout | `SignalStore`、`PreferenceService` | 偏好持久化、导出文件、操作审计 | 并发 loading 计数；离线数值和 sparkline 清空；错误统一格式化 |
| 实时曲线 | 信号组、暂停/继续、历史回放、CSV、快照 | `useSignalsStore`、页面回放状态 | curve-config、timeseries、replay、fault-events、selection/export/snapshot | `SignalStore`、历史查询、`PreferenceService` | SQLite 解码数据、偏好、CSV/快照、操作审计 | 离线 series 为空、当前值为 stale；回放错误进入 Toast + PageDataState |
| 手动控制 | 0x121 参数、预览、逐项反馈质量、联锁、发送/停止/急停 | `useControlStore` | status/interlock/manual-feedback/manual-curves；`POST /control/121/*` | `SafetyInterlockService`、TX scheduler、`SafeStopService` | 控制与拒绝操作审计；CAN/信号/DB 状态参与判定 | 每个反馈展示 present/age/quality/channel/range/checks/blocking；offline/stale 屏蔽值和曲线；运动按钮 fail-closed |
| 一键检测 | Mock 会话、步骤、断言、日志、报告 | `useEolStore` | `/eol/dashboard`、`/eol/sessions/*` | EOL engine、EOL UoW、断言引擎、报告生成 | SQLite 会话/步骤/断言/动作、报告文件、操作审计 | offline 禁止所有写动作，测量值/实时曲线标 stale；错误保留在 PageDataState/Toast |
| 告警诊断 | 告警矩阵、确认、放行申请、诊断导出、定位、safe-stop | `useAlarmsStore`、principal | `/alarms/dashboard`、ack/override/export/jump、layout | `AlarmService`、`OverrideService`、`SafeStopService` | alarms/operator_actions、偏好、导出文件 | 离线图表为空；按钮按角色和在线状态过滤；历史分页未实现且已禁用标注 |
| 报告管理 | 扫描、筛选、预览、导出、打印、取消/重试、删除 | `useReportsStore`、principal | `/reports/dashboard`、preview、export、printers、print-jobs、delete | `ReportService`、`PrintService` | 报告文件、打印 job、SQLite、报告 hash 与操作员审计 | 打印显示 queued/printing/completed/failed/cancelled；打印后端缺失即禁用；空报告和错误统一显示 |
| 历史追溯 | 筛选、动态操作员/工位、分页、详情、下载、回放 | `useHistoryStore`、principal | `/history/dashboard/export`、`/test-sessions/*` | `HistoryService`、报告/日志下载服务 | SQLite 会话/日志/断言、导出文件、下载/打开审计 | 查询失败不再提示“完成”；离线详情和趋势清空；空会话统一显示 |
| 系统设置 | import/export、dry-run/apply、backup/restore、cleanup、storage health、DBC | `useSettingsStore`、principal | config lifecycle、storage lifecycle、DBC、maintenance | 配置签名/校验/回滚、`BackupService`、`RetentionService`、`DbcService` | 签名配置、备份 manifest/hash、SQLite/config history/operator_actions | 操作级 loading/error；导入先 dry-run diff；失败不关闭预览；路径均为 data_root 派生且只读 |

## 权限矩阵

| 页面/动作 | viewer | operator | engineer | admin |
|---|---:|---:|---:|---:|
| 总览、CAN、信号、曲线、告警、报告、历史读取 | 是 | 是 | 是 | 是 |
| Network / Manual 页面 | 403 | 403 | 是 | 是 |
| Auto Test 页面 | 403 | 是 | 是 | 是 |
| System Settings 页面 | 403 | 403 | 是 | 是 |
| 普通导出、报告扫描、告警确认 | 否 | 是 | 是 | 是 |
| 手动控制、网络诊断 | 否 | 否 | 是 | 是 |
| 通道配置应用、配置 import/apply、备份恢复、cleanup、删除报告 | 否 | 否 | 否 | 是 |

直接访问无权路由跳转 `/forbidden`；直接调用 API 仍由后端返回 401/403。Electron E2E 使用 viewer 直达 `/network-config` 验证 403，不依赖菜单隐藏。

## 无页面级滚动约束

页面根节点继续采用 `height: 100% / min-height: 0 / overflow: hidden`，内部表格或列表自行滚动。Electron 在 1366×768 与 1920×1080 共采集 22 个页面实例，并将 `document.scrollingElement.scrollHeight > clientHeight + 1` 作为失败条件。
