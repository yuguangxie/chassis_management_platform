# 前端架构审计

> **历史基线 / 已被后续审计取代。** 当前结论见 [`current_audit_2026-07-23`](../current_audit_2026-07-23/00_AUDIT_INDEX.md) 和本轮 [P0/P1 验证索引](../verification/software-p0-p1-closure-2026-07-23/README.md)。

## 已验证优点

- Vue 3 Composition API、Pinia、Vue Router、TypeScript 能通过 `vue-tsc --noEmit`。
- 11 页共享 `AppShell/SidebarNav/TopStatusBar/WindowChrome`，深色 token 统一。
- ECharts 公共组件在 `onBeforeUnmount` 调用 `dispose` 并移除 window resize。
- 页面轮询 timer 多数在卸载时清理；离线 fallback 不出现大红横幅。
- Electron preload 开启 `contextIsolation:true`、`nodeIntegration:false`，仅暴露三项窗口控制 IPC。

## 关键问题

| 项目 | 结论 | 代码/证据 |
| --- | --- | --- |
| API 封装 | `apiGet` 丢弃错误 body；DELETE 无 headers/body 能力 | `desktop/src/api/http.ts:1-25` |
| WebSocket | 无 close/error/reconnect/off；所有页面订阅 `*`；handler 永不删除 | `desktop/src/api/websocket.ts:1-15` |
| 重复连接 | AppShell、页面和 store 都可能调用 connect | `stores/appStatus.ts:61-72`; `pages/*` |
| 请求放大 | `signals.timeseries.batch` 每条消息触发 HTTP GET | `stores/signals.ts:75-80` |
| CAN 重复 upsert | 同时消费 raw_frame 与 latest_frame_update | `stores/can.ts:130-136` |
| 曲线选择 | UI checkbox 与 series 不一致 | `RealtimeCurvePage.vue`; 运行截图 |
| 响应式 | AppShell `.content{overflow:auto}`；多页固定网格在 1366 裁切 | `AppShell.vue:22`; runtime metrics |
| 图表 resize | 只监听 window resize，无 ResizeObserver；首次 0 尺寸警告 | chart components; console evidence |
| 类型质量 | 搜索到 `any` 112 处；无 ts-ignore | `evidence/commands/search_bany_b.txt` |
| Mock 比例 | fallback 155、mock 201 处；真实/Mock 来源缺统一类型 | 搜索证据 |
| 错误边界 | 无全局 Vue error boundary；toast 解析方式各页不同 | pages/stores |
| preload | IPC 白名单较小是优点；未设置 Chromium sandbox/CSP | `electron/main.cjs`; `index.html` |
| Node API | renderer 未直接调用 Node API | 静态搜索通过 |
| 前端直发 CAN | 未发现；控制均走 HTTP 后端 | ManualControlPage/store |

## 生命周期结论

ECharts dispose 基本正确，但 WebSocket handler 和连接生命周期不正确。路由来回切换报告、历史、EOL、告警页面会持续注册 handler；长期运行风险为重复请求、重复 toast 和内存增长。建议将 WebSocket 订阅返回 unsubscribe，并由组件 scope 清理；图表改用 ResizeObserver。

## 硬编码和异常状态

页面具备完整 fallback 外观，但许多 API 本身也返回固定数据，导致 `backendOnline=true` 时仍显示 Mock 内容。应在 API 类型中加入 `data_source`, `mock`, `quality`, `updated_at`，生产模式禁止无标识 fallback。
