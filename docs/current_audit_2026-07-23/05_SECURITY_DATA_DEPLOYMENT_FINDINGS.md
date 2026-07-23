# 安全、数据与部署详细发现

## 1. 分级规则

- P0：阻止 production/真实车辆放行，或可破坏安全/配置/审计根信任。
- P1：进入现场或形成正式发行前应关闭；可导致追溯、可靠性、恢复或运维失败。
- P2：不阻止 Mock/内部验证，但应纳入近期质量改进。
- External Gate：需要硬件、证书、现场资产或组织流程，不能只靠仓库代码关闭。

## 2. P0 发现

| ID | 发现 | 证据 | 影响 | 必要整改 |
|---|---|---|---|---|
| P0-01 | production 通道配置绕过签名生命周期 | `backend/app/api/config.py:903-974` | 管理员可不经签名包改变 endpoint/control channel/runtime；单一配置权威失效 | production 返回 409/403 并引导 signed package，或把 endpoint 变更合并进签名 apply；补回滚/告警/审计测试 |
| P0-02 | 控制动作与操作审计非原子，审计异常被吞 | `backend/app/services/audit.py:24-51`；`backend/app/api/control.py:138-175` | 可能“已发 CAN/已启动周期发送，但审计未落库” | command intent/outbox + 状态机；审计失败锁存 DB fault、阻止新运动、不得报告完整成功 |
| P0-03 | hardware validated 没有签名、可撤销的生产授权模型 | `RuntimeConfig.safe_stop_policy_hardware_validated=false`；production schema 不含该字段 | 默认安全，但项目没有合法的真实运动放行路径；人工改 YAML 会绕过治理 | 独立 hardware acceptance artifact，双人审批、hash、有效期、撤销、现场测试引用 |
| P0-04 | 当前代码没有与其一致的正式发行证据 | 当前 dirty worktree；phase-06 包基线 `3c6c838` 且 dirty/unsigned | SBOM/hash/安装证据不能证明当前源码；供应链不可追溯 | clean commit、远程 CI、正式签名、同 commit 的 installer/SBOM/hash/manifest/安装证据 |
| EXT-P0-01 | 物理急停、安全 PLC/继电器、动力隔离没有证据 | 仓库只有软件急停/状态 | 软件/OS 崩溃时不能证明独立安全 | 由硬件/安全团队完成 FMEA、线路图、台架测试和签字 |
| EXT-P0-02 | safe-stop/watchdog/20 ms 控制在真实底盘未验证 | 仅 Mock/回环 | 停发/保持/超时后的真实车辆行为未知 | 隔离台架抓包和外部测量，确认 p95/p99 抖动、制动曲线、确认时序和失效行为 |

## 3. P1 发现

| ID | 发现 | 证据/现象 | 建议验收 |
|---|---|---|---|
| P1-01 | TCP transport 不具备生产重连 | `tcp_gateway.py` EOF 后退出；无 backoff/half-open | 服务端重启、拔线、半开、抖动、连接拒绝均进入明确状态并自动有界恢复；若不实现则 production schema 禁止 TCP |
| P1-02 | 通道直接重配丢失安全事件 callback | `CanGatewayManager(new_config, on_frame)` 未传 `on_can_security_event` | 非授权来源仍不更新缓存，且告警/审计持续可见；回滚后 callback 也保持 |
| P1-03 | EOL 创建使用演示默认标识 | `eol/models.py:36-43` | production 必须显式扫码/工单输入；VIN/底盘/序列号格式、车型、唯一性、重复件策略测试 |
| P1-04 | CAN source_session 固定演示值 | manager `S20260401-001`；store 相同 fallback | 无 active session 显示 `-`；有 session 绑定实际 ID；导出/报告交叉核对 |
| P1-05 | System Settings 版本/DBC 元数据伪值 | config `cfg-20260401`、Node `20.x`、请求时间作 build time；DBC 48/312 fallback | 全部来自 runtime config、test plan、release manifest、实际 DBC；unavailable 显示 0/未知而非固定数 |
| P1-06 | Network 字段语义混淆 | `tx_enabled` 被写入 `ChannelConfig.enabled`；CAN1 template `allow_tx:true` | 分离 receive enabled/control selected/active TX policy；服务端 active TX policy 不得被 UI 扩大 |
| P1-07 | Windows 网卡 identity 未验证 | schema 有 adapter_name，诊断未绑定实际 adapter | 核验接口索引、名称、MAC/IP，漂移时 production preflight 失败 |
| P1-08 | 应用日志无轮转/保留 | `logging.FileHandler` | 大小+时间轮转、压缩、保留、磁盘阈值、锁/只读失败和审计 |
| P1-09 | retention 配置未完整消费 | decoded/report/app logs 未自动清理；raw retention 只显示 | 每类数据都有 policy、dry-run、保护、批准、作业、失败恢复和审计；默认仍禁止无人值守危险删除 |
| P1-10 | 压缩配置键不一致 | YAML `compress_rotated`，lifecycle 读 `compress_after_days` | schema 拒绝未知字段；实际轮转后生成 gzip；状态显示真实配置 |
| P1-11 | Parquet 追加不可扩展 | append 时读全文件再写 | 分区/append-friendly writer；百万级/长稳态测试，或 production 禁用 Parquet |
| P1-12 | 当前 UI 收口未提交/未远程验证 | 37 个 tracked 修改和多项 untracked UI/证据 | 评审 diff、提交、Windows CI 全套、从 commit 打包，避免把本地证据当 release |
| P1-13 | 真实打印未验收 | virtual backend 通过，Windows spooler 只有实现/旧证据 | 目标打印机、普通用户、中文/空格、脱机/卡纸/取消/重试和报告 hash 抽查 |
| P1-14 | DBC/阈值/计划只证明 JD Mock | 只有一份 DBC 和 repository test plan | 每车型/固件批准 hash、信号语义、阈值、金样/坏样和版本兼容矩阵 |
| P1-15 | 生产长稳态与高帧率不足 | E2E 60 秒；可选 1000 fps/10 min CI 未启用 | 目标 IPC 上 8～24h soak、持续告警、1000fps、磁盘写入、内存/GPU/队列/抖动指标 |
| P1-16 | 本地忽略目录含 bootstrap 运行产物 | `docs/verification/phase-06/quality/python/data/auth/bootstrap-admin.secret` 被 gitignore 忽略 | 不读取/提交内容；发布、归档、共享前清理忽略的 data/auth/token/log 产物；CI artifact 设置短保留 |

## 4. P2 发现

| ID | 发现 | 建议 |
|---|---|---|
| P2-01 | frontend fallback 含逼真 VIN/底盘/报告/会话 | production profile 使用纯 empty/offline；只在显式 Mock profile 加载示例 |
| P2-02 | ECharts 原始 chunk 1.12 MB，gzip 接近 380 KB 预算 | 继续按图表模块 tree-shake/动态加载；保留预算门禁 |
| P2-03 | 前端 coverage 范围较窄，store 总覆盖较低 | 扩大 include 到 pages/stores/api/router/auth；逐步提高 lines/branches 门槛 |
| P2-04 | backend 若干 API 覆盖偏低 | 优先补 control、eol、can、config、websocket、tx scheduler 失败分支 |
| P2-05 | FastAPI `on_event` 和 TestClient/httpx 警告 | 迁移 lifespan；升级测试栈时锁版本并跑完整回归 |
| P2-06 | 旧审计文档与当前状态冲突 | 在 `docs/audit/AUDIT_INDEX.md` 明确历史/当前；旧报告首部加 superseded 提示 |
| P2-07 | `.env.example` 未列全部验证脚本变量 | 分开 runtime env 与 verification-only env 文档，避免把测试 token 名误认为生产固定 token |
| P2-08 | disabled UI 功能尚多 | 保持禁用；按业务价值逐项建 API/权限/审计/失败测试后再启用 |

## 5. 已关闭的历史重点问题

以下历史审计项在当前代码中已形成软件闭环，不应继续按“完全未实现”描述：

- command-to-feedback 依赖矩阵及 missing/stale/invalid/source/range 409。
- production DBC hash/车型/ready 检查。
- CAN ID 边界与 UDP source allowlist。
- assertions 运算符/边界/窗口/错误输入测试。
- override 双人审批/范围/TTL/撤销/不可绕过。
- 短期 session、本地 bootstrap、路由守卫、API RBAC、WS 过期处理。
- 签名配置包 dry-run/diff/apply/rollback。
- data_root、migration、backup/restore、cleanup、storage health。
- 四种报告格式和打印 job 状态机。
- Electron sidecar、动态端口、离线打包、SBOM/hash/manifest、unsigned 标识。
- 11 页主要 Stub 收口、中文化、布局、按钮、信号稳定和双分辨率 E2E。

“软件已关闭”不等于“现场已验收”。例如 safe-stop 的代码与 Mock 测试已完成，但硬件行为仍是 External P0。

## 6. 威胁模型简表

| 资产 | 攻击者/故障 | 边界 | 已有缓解 | 残余风险 |
|---|---|---|---|---|
| 车辆控制 | 误操作、恶意本机用户、失效反馈 | UI→API→Safety→CAN | RBAC、0x121 allowlist、CAN2、反馈矩阵、fail-closed | 物理安全链/硬件 watchdog 未证实；审计非原子 |
| 配置/DBC | 篡改 package、错车型/endpoint | 本机配置与 runtime | HMAC、schema、hash、diff、回滚 | 普通 channel endpoint 绕过签名；本地签名 key 保护待固化 |
| session/账户 | token 窃取、暴力尝试 | renderer/sessionStorage/local DB | 短期随机 token、hash、lockout、撤销、Electron 隔离 | 本机恶意管理员/内存提取；Windows ACL/DPAPI 待验收 |
| CAN 接收 | 非授权 UDP 注入、洪泛、异常帧 | 网卡/socket/codec | source allowlist、strict codec、队列、告警 | 直接重配后告警 callback 丢失；真实网络/固件未测 |
| 数据/报告 | 磁盘满、损坏、穿越、篡改、误删 | data_root/SQLite/files | 派生路径、migration、backup/hash、cleanup protection | log rotation/全类 retention/大规模恢复不足 |
| 发行包 | 供应链篡改、旧包/降级 | CI→artifact→IPC | SBOM、hash、manifest、禁止降级新库 | unsigned；当前源码和现有包不一致 |

## 7. 机密与日志审计

- `git ls-files` 未发现以 secret/token/password/credential/key/pem 命名的已跟踪凭据文件。
- sidecar 短期凭据有日志脱敏测试；renderer 使用 sessionStorage，Electron 重启不保留业务 session。
- 一次性 bootstrap 文件位于 data_root/auth 并受 gitignore；当前工作区的旧验证 data 中仍有被忽略的 secret 文件名。审计未读取其内容，但发布/归档前必须清理。
- API/sidecar/验证脚本应继续禁止把 Authorization、bootstrap secret、HMAC key、session token 写入日志或证据 JSON。
