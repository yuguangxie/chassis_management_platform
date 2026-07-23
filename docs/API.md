# API：身份、授权、配置与安全联锁

## 2026-07-23 软件 P0/P1 收口

- production 的 `PUT /config`、`PUT /config/channels`、`POST /config/restore-safe-defaults`、`POST /config/channels/restore-defaults` 均拒绝普通直改，统一返回 HTTP 409 / `SIGNED_CONFIG_REQUIRED`，并先写拒绝审计。
- 唯一生产变更流程为 `POST /config/import` → schema/版本/签名校验 → dry-run/diff → 管理员确认 → `POST /config/apply` → blocking health → 原子切换或完整回滚。
- `GET /control/hardware-acceptance` 是只读接口；不存在普通写接口。production 普通运动在 artifact 缺失、签名错、过期、撤销、职责未分离或范围/hash 不匹配时返回 409，规则包含 `rule/label/current/threshold/blocking`。
- `POST /eol/sessions` 不再接受 operator/station 覆盖，也没有演示默认值；operator 取当前 principal，station 取当前已应用配置。请求字段为底盘号、VIN、序列号、车型、工单、计划、重复策略和显式 Mock 标志。
- 危险动作的审计或 control intent 持久化失败统一返回 503，且锁存数据库/审计故障；不能返回完整成功。
- 当前 OpenAPI 由 `scripts/generate_api_docs.py` 从运行模型生成，共 151 个 operation；`docs/api-authorization-matrix.csv` 为对应 RBAC 清单。

后端 REST 前缀为 `/api/v1`，WebSocket 为 `/ws`。控制 API 全部经过 `SafetyInterlockService`。本页记录 2026-07-22 P0/P1 收口涉及的契约。

## 当前契约快照

- 机器生成 OpenAPI：`docs/openapi.json`。
- 全量数据分类和最低角色（150 个 HTTP 操作）：`docs/api-authorization-matrix.csv`。
- 生产配置与签名包 schema：`docs/production-configuration.schema.json`。
- 生成命令：`python scripts/generate_api_docs.py`。生成器发现未分类路由时失败，禁止手工维护一份与代码漂移的接口清单。

## 身份 API 与会话状态

| 方法 | 路径 | 公开/角色 | 说明 |
|---|---|---|---|
| GET | `/auth/bootstrap/status` | 公开 | 只返回是否需要首次初始化及凭据来源类型 |
| POST | `/auth/bootstrap` | 公开、一次性 | 使用本机一次性 bootstrap secret 建立首个 admin 和 15 分钟默认会话 |
| POST | `/auth/login` | 公开 | 本地账户登录；连续失败默认 5 次后锁定 300 秒 |
| POST | `/auth/unlock` | 公开 | 密码重验并替换锁屏会话 |
| GET | `/auth/me` | viewer | 返回后端 principal、到期时间和权限，不返回 token |
| POST | `/auth/lock`、`/auth/logout` | viewer | 锁屏或撤销当前会话 |
| POST | `/auth/accounts` | admin | 建立 viewer/operator/engineer/admin 本地账户 |
| GET/POST | `/auth/sessions`、`/auth/sessions/{id}/revoke` | admin | 盘点和撤销会话 |

会话状态为 `ACTIVE -> LOCKED/REVOKED/EXPIRED`，终态不可恢复；解锁和再次登录总是签发新随机短期 token。数据库只保存 token SHA-256，不保存明文。账号密码使用每账号随机 salt 的 scrypt。前端只在 `sessionStorage` 保存当前进程会话，不使用 Vite build-time token，也不使用 localStorage 长期保留。刷新保留当前 Electron 窗口会话；Electron 完全重启要求重新登录。

## 数据分类与角色原则

`GET /health` 是唯一普通公开探针，仅返回 `{"status":"ok"}`。bootstrap/login/unlock 是受限公开身份入口。dashboard、signals、CAN、alarm、report、history、配置和审计均为敏感数据，至少需要 viewer。

## 数据生命周期与打印

| API | 最低角色 | 关键前置条件 |
|---|---|---|
| `GET /api/v1/storage/stats` | viewer | 返回实际测量，不合成容量 |
| `GET /api/v1/storage/schema-version` | viewer | 数据库已初始化 |
| `POST /api/v1/storage/health/recheck` | admin | 全部检查通过后才解除存储告警 |
| `GET/POST /api/v1/storage/backups` | admin | POST 使用 SQLite online backup |
| `GET /api/v1/storage/backups/{id}/validate` | admin | 校验 manifest、大小、hash、schema |
| `POST /api/v1/storage/backups/{id}/restore` | admin | 无活动会话；`RESTORE <id>`；先保留 rollback |
| `POST /api/v1/storage/cleanup/preview` | admin | 必须先 dry-run |
| `POST /api/v1/storage/cleanup` | admin | `confirmation=CLEANUP` |
| `GET/POST /api/v1/storage/cleanup/{id}[/cancel]` | admin | 查询进度或请求批次间取消 |
| `POST /api/v1/reports/{id}/archive` | admin | 文件存在且 hash 可计算 |
| `GET /api/v1/reports/printers` | viewer | 返回后端/OS 实际枚举结果 |
| `POST /api/v1/reports/{id}/print` | operator | `preview_confirmed=true`，PDF 和打印机可用 |
| `GET /api/v1/reports/print-jobs/{id}` | viewer | 持久化任务存在 |
| `POST /api/v1/reports/print-jobs/{id}/cancel|retry` | operator | 状态允许转换；重试前报告 hash 不变 |

请求体和新增响应均由 pydantic 明确类型。所有时间字段为 UTC ISO8601。完整机器可读定义见 `openapi.json`。

| 能力 | viewer | operator | engineer | admin |
|---|---:|---:|---:|---:|
| 敏感读取、下载已授权资料、回放导航 | 是 | 是 | 是 | 是 |
| 执行 EOL、确认告警、业务导出/打印 | 否 | 是 | 是 | 是 |
| 0x121 手动控制、CAN 连接/诊断、普通配置、DBC 重载 | 否 | 否 | 是 | 是 |
| 账户/会话、签名配置包、通道重配置、维护模式、报告删除 | 否 | 否 | 否 | 是 |

菜单、路由和按钮只用于减少误操作；每个 API 的后端依赖才是权限真源。`X-Role`、请求体 `role` 等客户端字段不能提升 principal。精确到每个方法和路径的矩阵见生成 CSV。

## 配置包 API

| 方法 | 路径 | 角色 | 语义 |
|---|---|---|---|
| GET | `/config/export` | admin | 由后端使用本机运行时 HMAC key 签出当前配置 |
| POST | `/config/import` | admin | 强制 `dry_run=true`，验证 schema/version/signature/profile，返回 diff、预检与阻断项，不修改状态 |
| POST | `/config/apply` | admin | 要求 `confirmation=APPLY` 和原因；重验、停止旧通道、启动新通道、健康检查、原子持久化；失败恢复旧 manager 和旧 package |

production 应用还要求 DBC loaded/full hash/车型完全匹配、数据根目录和数据库可写、EOL/周期控制空闲；新 UDP 通道必须在超时内收到批准来源帧。任何失败返回 409/503 并保持或回滚到原配置。production 启动本身要求已有签名 active package，仓库模板不能启动生产模式。

## WebSocket 认证

WebSocket URL 不含 token。客户端提供子协议 `chassis-session` 与 `chassis-token.<短期令牌>`，服务端只协商返回固定的 `chassis-session`。连接建立时及每 5 秒重验会话；过期、锁定或撤销以 4401 关闭。前端收到 4401 后清空会话、停止指数重连并跳转登录页，避免重连风暴。

## 统一错误

- `401 AUTH_REQUIRED/INVALID_TOKEN/SESSION_EXPIRED/SESSION_REVOKED/SESSION_LOCKED`：未认证或会话不可用。
- `403 INSUFFICIENT_ROLE`：principal 角色不足。
- `409 INTERLOCK_BLOCKED`：安全联锁阻断；详情含 rule/label/current/threshold/blocking。
- `409 CONFIG_PROFILE_MISMATCH/CONFIG_HEALTH_CHECK_FAILED`：配置不兼容或预检失败。
- `422 VALIDATION_ERROR/CONFIG_SIGNATURE_INVALID`：Pydantic/schema 或签名失败。
- `503 CONFIG_SIGNING_KEY_REQUIRED/CONFIG_APPLY_ROLLED_BACK`：本机密钥缺失或应用失败已回滚。

所有 HTTP 错误携带 UTC trace id；认证、安全拒绝、配置预览/应用/回滚和管理员会话操作写入操作审计。请求和日志不得记录密码、bootstrap secret、签名 key 或 bearer token。

## 控制请求与 409

`POST /control/121/send-once` 和 `POST /control/121/start-periodic` 接受原控制字段，并可选携带：

```json
{
  "gear": "D",
  "target_speed": 1.0,
  "front_steer": 0,
  "brake_enable": false,
  "safety_context": {
    "override_id": "OVR-...",
    "session_id": "EOL-...",
    "vehicle_id": "YL-JD-001"
  }
}
```

当前认证用户由服务端 principal 写入作用域，客户端不能伪造 actor。未提供 `safety_context` 时默认没有 Override。字段缺失或多余返回 422。

联锁阻断统一返回 HTTP 409：

```json
{
  "code": "INTERLOCK_BLOCKED",
  "message": "安全联锁阻止控制",
  "details": {
    "allowed": false,
    "profile": "test",
    "degraded_mode": false,
    "reasons": [
      {
        "rule": "feedback_steering_front_steering",
        "label": "前转角反馈",
        "status": "FAIL",
        "current": {"value": null, "checks": {"present": false}},
        "threshold": {"max_age_ms": 500, "channel": "CAN1", "can_ids": ["0xE1"]},
        "blocking": true
      }
    ]
  },
  "trace_id": "..."
}
```

## Override API

| Method | Path | 最低角色 | 说明 |
|---|---|---|---|
| GET | `/alarms/overrides` | viewer | 列出最近授权及状态 |
| POST | `/alarms/{alarm_id}/override-request` | engineer | 创建待独立审批申请 |
| POST | `/alarms/overrides/{override_id}/approve` | admin | 独立批准 |
| POST | `/alarms/overrides/{override_id}/revoke` | admin | 撤销待审或已批准授权 |

申请体：

```json
{
  "reason": "受控诊断需要",
  "session_id": "EOL-...",
  "operation": "manual",
  "vehicle_id": "YL-JD-001",
  "authorized_user": "operator-a",
  "duration_seconds": 300
}
```

`operation` 当前仅允许 `manual`；EOL 不接受告警 Override，保持保守阻断。批准体必须为 `{"confirmation":"APPROVE","reason":"..."}`；申请人与批准人相同返回 409 `SEPARATION_OF_DUTIES`。撤销体为 `{"reason":"..."}`。不存在返回 404，其余状态冲突返回 409。

Override 只影响精确的单个严重告警规则，不能改变其他联锁结果。所有时间戳为 UTC ISO8601，响应和日志不包含 bearer token。

## Safe-stop 响应补充

`POST /control/safe-stop` 和 `/control/emergency-stop` 成功确认后返回 `post_confirmation_policy`、`hold_active` 与 `hardware_validated`。解除急停和 `/control/reset-defaults` 使用同一可信反馈/DBC/数据库/告警联锁，失败返回 409。

## 打包 sidecar 边界

安装态由 Electron 生成每次启动随机凭据。除最小 `/api/v1/health` 外，HTTP 请求先要求 `X-Chassis-Sidecar`，随后仍执行用户 session 和角色鉴权；WebSocket 同时要求 `chassis-sidecar.<credential>` 与 `chassis-token.<session>` 子协议。凭据缺失返回 403/4403，不得写入日志或 OpenAPI 静态示例。

`GET /internal/sidecar/readiness` 和 `POST /internal/sidecar/shutdown` 不进入 OpenAPI，且只供本机 Electron 主进程使用。readiness 是软件进程状态，不是车辆 ready，也不放宽任何控制联锁。

## Signals dashboard HTTP/WS 同形约定（2026-07-23）

`GET /signals/dashboard` 与 WebSocket topic `signals.dashboard` 现在都发布完整 dashboard response：业务字段之外包含顶层 `quality`、`status`、`mock`、`updated_at`、`data_source` 和 `trace_id`。`status.quality` 为兼容字段，其值必须与顶层 `quality` 一致。

前端允许兼容旧 publisher 的 `payload.status.quality`，但缺失的增量字段不得覆盖当前完整快照。`stale`、`invalid`、`unavailable` 和 Mock 标记不能被提升为真实 fresh 数据，也不能用于控制安全判断。

`GET /control/manual-curves` 的横轴从存储的 UTC ISO8601 生成 `HH:mm:ss` 显示标签；存储值仍保持完整 UTC ISO8601，不改变追溯精度。

本轮未增加或删除 OpenAPI path，也未改变 pydantic API 字段，因此无需生成新的结构版本；响应同形契约由 `test_phase03_contract_data.py` 覆盖。
