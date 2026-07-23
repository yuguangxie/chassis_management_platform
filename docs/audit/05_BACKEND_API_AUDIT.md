# FastAPI 与接口审计

> **历史基线 / 已被后续审计取代。** 当前结论见 [`current_audit_2026-07-23`](../current_audit_2026-07-23/00_AUDIT_INDEX.md) 和本轮 [P0/P1 验证索引](../verification/software-p0-p1-closure-2026-07-23/README.md)。

## 自动枚举与覆盖

- OpenAPI：112 个 HTTP operation，完整清单 [openapi_routes.csv](evidence/api/openapi_routes.csv)。
- 资料包核心规范：31 个 operation；路径归一化后 31/31 有对应路由，路由覆盖率 100%。
- 路径参数名有 10 处 `{id}` 对 `{sid}/{rid}` 差异，不影响路由但影响契约一致性。
- 选择 56 个页面/按钮接口实测，均返回 HTTP 200；其中至少 16 个明确 `stub:true`。
- 核心 31 接口按语义保守分类：REAL 8、PARTIAL 13、STUB 4、MOCK 6、MISSING 0；真实实现率约 **25.8%**。这不是 OpenAPI 路由覆盖率。

证据：[API probe summary](evidence/api/api_probe_summary.json)、[API spec comparison](evidence/api/api_spec_comparison.json)、每个响应在 `evidence/api/*.json`。

## 主要接口组

| 组 | 路由状态 | 真实状态 |
| --- | --- | --- |
| health/DBC | 存在 | DBC status/reload 真实，39 messages/170 signals |
| CAN channel | 存在 | UDP start/stop/receive 真实；TCP 不存在；self-test Stub |
| CAN monitor | 存在 | latest 聚合真实；decode details/statistics/export 多为 Mock/Stub |
| signals | 存在 | current 部分真实；dashboard/timeseries 混合 fallback；保存/导出 Stub |
| control | 存在 | 0x121 send/scheduler 真实；状态展示和安全停车不完整 |
| EOL | 存在 | 内存演示状态机；暂停/中止/急停语义失败 |
| alarms | 存在 | 当前告警部分真实；历史/建议/导出/放行多为 Mock/Stub |
| reports/history | 存在 | 扫描少量真实，列表/预览/下载/趋势多为 Mock/Stub |
| config/system | 存在 | DBC、原子配置、历史部分真实；导入/导出 Stub，权限不可信 |

## 契约与异常

- Pydantic 在系统配置、维护和 0x121 命令等部分路径使用；许多 dashboard 直接返回 dict，无 response model。
- 全局 500 handler 返回平铺 `{code,message,details,trace_id}`，FastAPI HTTPException 则返回 `{detail:...}`；trace_id 多为空。
- `apiGet` 对非 2xx 只保留 status text，前端拿不到结构化原因。
- CORS 接受任意 Origin 且 credentials=true；安全探测中恶意 Origin 被回显。
- 无 OpenAPI security scheme、认证中间件和可信用户上下文。
- 部分 config/report 操作写 operator_actions/config_history，但控制、EOL 和导出链路不完整。
- 文件删除虽限制 `REPORTS_DIR`，但角色仅由 header 声明；不存在 ID 被 `_find_report` 回退为 Mock，错误返回成功。

## WebSocket

3 秒观察实际收到 5,292 条消息：`can.raw_frame`, `can.latest_frame_update`, `can.decoded_frame`, `can.statistics`, `signals.current`, `signals.dashboard`, `signals.timeseries.batch` 各 744 条，`alarms.current` 84 条。文档要求 statistics 1Hz、signals 约 10Hz，当前实现严重超发。WebSocket 无发送队列、节流、背压、客户端慢消费隔离。
