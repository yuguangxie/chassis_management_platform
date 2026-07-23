# 真实环境运行与生产就绪度审计

## 1. 直接回答

当前项目：

- 可以在开发机以 Mock/回环完整联调方式运行。
- 可以构建并验证 unsigned 内部 Windows 安装包；首次启动默认 Mock/离线，不自动连接现场设备或发送 CAN。
- 在补齐生产签名配置并关闭本审计 P0 后，可进入“真实适配器只监听、车轮离地/执行器断能”的诊断阶段。
- **不可以直接接入能够运动的真实底盘并作为生产 EOL 系统投用。**

原因不是单一代码错误，而是发布、配置权威、物理安全、硬件时序、真实协议、车型 DBC、追溯、打印和量产测量系统均未完成最终验收。

## 2. 分层就绪判定

| 层级 | 允许能力 | 当前状态 | 条件 |
|---|---|---|---|
| A 开发/单测 | 临时目录、Mock、127.0.0.1 | PASS | 当前可执行 |
| B 完整 Mock 联调 | Electron + sidecar + simulator，11 页 | PASS（本机） | 不访问非回环，不发送真实 CAN |
| C unsigned 内部安装 | 无 Node/Python/互联网的 Windows 测试机 | CONDITIONAL PASS | 仅内测；现有包不是当前工作树，也未签名 |
| D 真实 CAN 只监听 | USR-CAN115 + 批准源，执行器断能 | NOT EXECUTED | 先关闭 production 配置绕过并生成签名 RC |
| E 静态通电台架 | 车辆固定/车轮离地，物理急停有效 | NOT READY | 完成物理安全链、DBC、心跳和异常源测试 |
| F 低速封闭运动台架 | 有安全员、限速、隔离区 | NOT READY | safe-stop/watchdog/急停/制动实测全部通过 |
| G 产线试点 | 受控班次、金样/坏样、追溯抽查 | NOT READY | GR&R、节拍、恢复、打印、签名发行和 SOP |
| H 正式量产 | 持续运维、升级回滚、审计复核 | NOT READY | 所有 release/现场/安全/质量门禁签字 |

## 3. production profile 当前行为

production 的正向安全条件包括：

- FastAPI 仍只应绑定 localhost；renderer 通过 sidecar 短期通信凭据访问。
- 必须有签名 active config package，车型、完整 DBC SHA-256、test plan、station、data_root、printer 和 endpoint allowlist 由 package 指定。
- DBC 必须 loaded、hash 完整匹配、车型一致。
- 普通运动命令要求数据库可写、无急停、无严重告警、队列健康和对应反馈矩阵全部通过。
- CAN manager 只允许 control channel CAN2，并只允许 ID 0x121。
- `safe_stop_policy_hardware_validated` 默认为 false；production 普通运动因此 fail-closed。

这意味着即使把 runtime profile 改成 production，项目也不会自动成为可运动系统。当前签名配置 model 没有硬件验收引用/签名字段，不能通过受控配置生命周期把 `hardware_validated` 安全地变为 true；直接改仓库 `configs/safety_interlock.yaml` 不应被当作生产批准流程。

## 4. 上线前软件 P0 门禁

### P0-SW-01 配置单一权威

production 禁止普通 `PUT /config/channels` 和 restore-defaults 直接修改 runtime/文件。所有 endpoint、allowlist、enabled/control channel 必须来自签名 package，且 apply 后完成 bind、批准来源收帧、DBC、data_root 和 DB 写健康检查；失败完整回滚。

### P0-SW-02 审计可靠性

运动控制、安全拒绝、override、配置、恢复、cleanup 和打印危险动作必须证明操作审计已持久化。控制发送与审计失败不能形成“动作成功、审计丢失”；发生不可恢复审计错误时锁存存储故障并阻止后续运动。

### P0-SW-03 硬件验收授权模型

建立独立、签名、不可由普通 UI 自行修改的 hardware acceptance artifact，至少包含工位、车辆系列、控制器/固件、物理急停/PLC、safe-stop policy、watchdog、测试报告 hash、批准人、有效期和撤销状态。没有有效 artifact 时 production 普通运动继续 409。

### P0-REL-01 当前版本可追溯发行

清理工作树并形成审查提交；由远程 Windows CI 从该 commit 生成 SBOM、漏洞报告、release manifest、artifact hash 和正式签名安装包；安装、升级、回滚、卸载证据的 commit/hash 必须完全一致。

## 5. 现场硬件验收矩阵

| 项目 | 必须证明 | 当前证据 |
|---|---|---|
| 物理急停 | 按下后独立切断/禁止驱动；软件只读状态与物理状态一致；复位需人工确认 | 无 |
| 安全 PLC/继电器 | 软件失效时仍能阻止危险运动；线路开路/短路被检测 | 无 |
| 控制器 watchdog | 0x121 停发、超时、抖动、重复帧、旧帧时底盘行为 | 无 |
| safe-stop | 制动请求、速度下降、制动反馈、确认后停发/保持策略的真实波形 | 仅 Mock |
| USR-CAN115 UDP | 实际固件、源端口、标准/扩展、异常 DLC/RTR、丢包/乱序/洪泛 | 仅 codec/回环 |
| USR-CAN115 TCP | 断线、半开、重连、设备重启、网络抖动 | transport 未完成 |
| 双 CAN 通道 | CAN1 只接收、CAN2 控制；错接线/互换/重复源均 fail-closed | 仅 Mock |
| DBC | 所有目标车型、控制器固件和实车信号缩放/端序/枚举签字 | 仅 JD 文件/Mock |
| 关键反馈 | 速度、挡位、驱动、转角、制动、心跳的周期、质量、范围和 source | 仅配置/Mock |
| 制动/转向/驱动 | 边界值、跟随、超时、卡滞、反向、传感器错误 | 仅断言模型 |
| 电源/休眠 | 断电、IPC 休眠、网卡重置、磁盘满/锁、进程崩溃后的安全状态 | 部分软件注入 |
| 打印 | 目标打印机、驱动、默认/脱机/卡纸/取消/重试、纸张版式 | 仅虚拟后端 |

## 6. 现场配置与资产准备

生产现场必须本地生成且不得提交仓库：

1. 正式签名安装包及发布 hash。
2. production signed config：实际 station、Windows adapter identity、CAN endpoint/source allowlist、vehicle series、批准 DBC hash、test plan、绝对 data_root、printer。
3. 配置签名密钥，存放在 Windows 受控秘密存储/ACL 中；不得作为环境明文长期散落。
4. 一次性 bootstrap secret；管理员初始化后确认文件删除/失效，记录审计但不记录 secret。
5. 现场账户和角色分配；操作员/工程师/管理员分离。
6. DBC、test plan、阈值、报告模板、hardware acceptance artifact 的批准记录。
7. 备份目标、保留策略、磁盘告警、恢复演练和审计复核 SOP。

模板中的 127.0.0.1、zero DBC hash 和 `REPLACE_WITH_*` 只能用于占位；不得直接作为现场配置。

## 7. 推荐的首次现场验证顺序

1. 在断网干净 Windows VM 上安装正式签名 RC，验证 hash、签名、SBOM、卸载数据保留。
2. 不连接 CAN，完成 bootstrap、角色、signed config dry-run、data_root、DB migration、backup/restore、虚拟打印。
3. 连接真实 USR-CAN115，但车辆执行器断能；只允许接收，验证 source allowlist、online/stale、DBC、错误帧和拔线。
4. 接入物理急停/PLC，只验证输入与联锁，不发运动命令。
5. 车辆固定/车轮离地，按审批测试执行 0x121 零速/制动和 safe-stop；抓取 CAN 与外部测量数据。
6. 验证 watchdog、停发、网络断开、数据库不可写、严重告警、队列洪泛、进程崩溃。
7. 通过安全评审后，在封闭区以独立安全员、最低限速和明确终止条件进行低速动作。
8. 完成金样/坏样、重复性/再现性、报告/打印/追溯抽查后才进入产线试点。

## 8. 终止条件

任何阶段出现以下情况应立即停止升级门禁：

- 非批准 CAN ID 或 CAN1 出现主动发送。
- 未授权 UDP source 更新 online、last_frame 或 signal cache。
- missing/stale/invalid/out-of-range 反馈仍允许运动。
- 审计写入失败但 API/页面报告动作成功。
- safe-stop 未在批准时间内得到新鲜速度/制动确认。
- 物理急停、PLC 或 watchdog 的实际行为与批准模型不一致。
- DBC hash、车型、plan、config、release manifest 任何一项不一致。
- 数据库只读/损坏、磁盘不足、队列异常或严重告警下仍能开始新运动。

## 9. 生产放行结论模板

当前应填写：

```text
Mock/回环软件验证：通过
当前工作树远程 Windows CI：未执行
当前工作树正式签名安装包：不存在
真实 CAN 只监听：未执行
物理安全链：未验证
safe-stop/watchdog：未验证
车型/DBC/计划现场签字：未完成
真实打印/恢复/长稳态：未完成
生产放行：拒绝（NOT_READY）
```
