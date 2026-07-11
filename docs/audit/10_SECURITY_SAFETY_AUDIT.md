# 安全与安全联锁审计

| 检查 | 结果 | 依据 |
| --- | --- | --- |
| UI 直接发 CAN | 通过 | 未发现 renderer socket/Node API，均走后端 HTTP |
| 控制经后端 | 通过 | ManualControl store 调用 /control |
| 所有控制经 SafetyInterlock | 部分 | send/start/safe-stop 调用；EOL 不调用；急停另行处理 |
| 控制通道唯一 | 部分 | 配置 gate 存在，默认 CAN2；无认证 |
| 急停优先级 | 失败 | 不发送停车帧；EOL 不停止 |
| 安全停车 | 失败 | 单次发送，无反馈确认 |
| 关键报文在线 | 失败 | 用处理时间，积压可伪在线 |
| 严重告警 | 部分 | 手动发送 interlock 检查；EOL/展示不一致 |
| 速度/转角限制 | 通过（编码 API） | 超速阻断、转角 clamp 测试通过 |
| 看门狗 | 失败 | UI 固定 OK(120ms)，无 watchdog service |
| 数据库不可写 | 部分 | 启动时检查一次；EOL 运行中不检查 |
| DBC 未加载 | 部分 | 可配置 raw control；EOL 不检查 |
| 0x123/0x126/NMT 默认关 | 通过默认值 | gate 单测通过 |
| 维护模式管理员确认 | 失败可信身份 | 确认文本存在，但请求可自称 admin |
| 人工放行 | Stub | 无审批流 |
| 报告删除 | 失败 | x-role 可伪造；前端又无法正常发送 |
| 配置导入 | Stub | 未解析文件 |
| 路径穿越 | 部分 | 删除有父目录检查；其余文件操作多为 Stub |
| Electron isolation | 基本通过 | contextIsolation true、nodeIntegration false；无 sandbox/CSP |
| CORS | 失败 | 任意 Origin + credentials |
| 认证授权 | 失败 | 无 auth scheme，默认 admin |
| Mock 标识 | 失败 | 部分固定 API 不标 mock，顶部可显示关闭 |
| 异常保守失败 | 失败 | EOL 断链/转向/制动故障可 PASS |

## 动态安全证据

1. 超速与已触发急停时手动 send-once 被 409 阻断。
2. EOL pause/abort/emergency 不停止后台任务。
3. 两通道断开时 EOL 仍 PASS。
4. 约 1000fps 压力后停止 simulator 5 秒，CAN2 仍 online 且控制请求 200。
5. 无认证可进入 maintenance；`x-role:admin` 可使不存在报告删除返回 200。
6. 任意 Origin CORS 预检被允许。

## P0

SAFE-001 至 SAFE-005 均可能造成错误车辆动作、错误放行或无授权控制。安全评分 **28/100**。在这些问题关闭并由独立故障注入测试证明前，禁止连接真实车辆。

## Electron

无原生菜单、无框窗口和 IPC 白名单符合目标；仍需 `sandbox:true`、CSP、导航/新窗口限制以及生产 URL 白名单。renderer 未发现直接 Node/CAN 访问。
