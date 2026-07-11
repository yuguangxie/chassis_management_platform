# 问题登记

共 42 项：P0=5、P1=12、P2=19、P3=6。

| ID | 级别 | 分类 | 模块 | 标题 | 阻产 | 车辆安全 | 工作量 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SAFE-001 | P0 | 安全 | EOL 状态机 | 暂停、中止和急停不停止 EOL 执行任务 | 是 | 是 | L | OPEN |
| SAFE-002 | P0 | 安全 | EOL/联锁 | CAN1/CAN2 断开时一键检测仍 PASS | 是 | 是 | L | OPEN |
| SAFE-003 | P0 | 安全 | CAN/联锁 | 高负载积压帧使设备断开后仍被判在线并允许控制 | 是 | 是 | L | OPEN |
| SAFE-004 | P0 | 安全/权限 | 认证授权 | 后端无认证且默认角色为 admin | 是 | 是 | L | OPEN |
| SAFE-005 | P0 | 安全 | 急停 | 急停只停止周期任务并置位，不下发零速/制动帧 | 是 | 是 | M | OPEN |
| EOL-001 | P1 | 检测 | 故障判定 | 转向无响应和制动失败 profile 错误 PASS | 是 | 是 | L | OPEN |
| EOL-002 | P1 | 检测 | 步骤语义 | 低 SOC/告警在第 1 步失败且引擎忽略测试计划 | 是 | 是 | L | OPEN |
| SAFE-006 | P1 | 安全/UI | 手动控制 | UI 0x121 Byte 预览与实际发送 payload 不一致 | 是 | 是 | M | OPEN |
| SAFE-007 | P1 | 安全/UI | 手动控制 | 联锁展示接口固定显示允许发送 | 是 | 是 | S | OPEN |
| SAFE-008 | P1 | 安全 | 安全停车 | 安全停车仅发送一次且不验证车辆停止 | 是 | 是 | M | OPEN |
| PERF-001 | P1 | 性能 | CAN 接收 | 目标约 1045fps 时实际仅处理 345.9fps并形成长尾积压 | 是 | 是 | L | OPEN |
| API-001 | P1 | API/WebSocket | 实时推送 | 每帧顺序广播 7 个大 topic，前端每次 timeseries 又发 HTTP | 是 | 否 | M | OPEN |
| DB-001 | P1 | 数据 | 持久化 | EOL/CAN/信号/告警/报告核心表均为 0 行 | 是 | 否 | L | OPEN |
| REPORT-001 | P1 | 报告 | 生成器 | 生成的 DOCX 中文乱码，PDF 中文方块且仅含会话/结果 | 是 | 否 | L | OPEN |
| DEPLOY-001 | P1 | 部署 | Electron | electron:build 只执行 Vite，main.cjs 生产仍加载 5173且不拉起后端 | 是 | 否 | L | OPEN |
| SIM-001 | P1 | 仿真 | 开发配置 | 默认发送地址是 [REDACTED_CAN1_GATEWAY]/99:1234，与仿真器 127.0.0.1:12341/2 不匹配 | 是 | 是 | M | OPEN |
| DB-002 | P1 | 日志 | 原始 CAN | 所有帧同步追加到单个 raw_can_current.csv，无轮转/容量上限 | 是 | 否 | M | OPEN |
| DBC-001 | P2 | 协议 | USR-CAN115 | UDP 半包跨数据报拼接且没有重同步 | 是 | 是 | M | OPEN |
| CAN-001 | P2 | CAN | 统计 | fps 使用启动以来累计平均而非滚动窗口 | 否 | 否 | S | OPEN |
| CAN-002 | P2 | CAN | 缓存 | recent_frames 仅 2,000 帧，低于资料包每通道至少 10,000 建议 | 否 | 否 | S | OPEN |
| DBC-002 | P2 | DBC | 0x102 | 运行解码只产生总 bitmap，监控详情中的保护位为固定数据 | 否 | 是 | M | OPEN |
| API-002 | P2 | API | Dashboard | 大量固定数据返回 200 且未统一标识 Mock | 否 | 是 | M | OPEN |
| API-003 | P2 | API | 错误处理 | 错误响应结构和 trace_id 不统一 | 否 | 否 | M | OPEN |
| API-004 | P2 | API/CAN | 协议配置 | 接口允许 TCP 但运行时不存在 TCP gateway | 否 | 否 | M | OPEN |
| API-005 | P2 | API/权限 | 报告删除 | 前端 DELETE 不发送 x-role，后端又把不存在 ID 回退为 Mock 报告 | 否 | 否 | M | OPEN |
| UI-001 | P2 | UI | 响应式 | 1366×768 多页裁切或需页面滚动 | 否 | 否 | L | OPEN |
| UI-002 | P2 | UI | 顶部状态 | 页面主体收到实时数据时顶部 CAN1/CAN2 仍可显示 offline | 否 | 是 | M | OPEN |
| UI-003 | P2 | UI | 实时曲线 | 显示 0/256 已选择但六图仍有所有曲线 | 否 | 否 | M | OPEN |
| UI-004 | P2 | UI | 手动控制 | 存在 4 个白底原生输入控件 | 否 | 否 | S | OPEN |
| PERF-002 | P2 | 前端 | WebSocket 生命周期 | WsClient 无 close/error/reconnect/off，页面 handler 不注销 | 否 | 否 | M | OPEN |
| DB-003 | P2 | 日志 | 解码信号 | SignalLogWriter.write 是空函数 | 是 | 否 | M | OPEN |
| DB-004 | P2 | 数据库 | 事务 | 每条 execute 立即 commit，无会话事务/回滚；shutdown 未 close 数据库 | 否 | 否 | M | OPEN |
| TEST-001 | P2 | 测试 | 仿真器 | 从项目根执行 pytest simulator/tests 收集失败 | 否 | 否 | S | OPEN |
| TEST-002 | P2 | 测试 | 前端/覆盖率 | 无 npm test、lint，后端未安装 pytest-cov | 否 | 否 | M | OPEN |
| DEPLOY-002 | P2 | 依赖 | npm | npm audit 报 2 high + 2 moderate | 否 | 否 | M | OPEN |
| REPORT-002 | P2 | 报告/UI | 预览 | 预览面板不读取真实 DOCX/PDF | 否 | 否 | M | OPEN |
| UI-005 | P3 | UI | 视觉还原 | 10 页像素差异仍为 28.7%~40.0% 像素超过阈值 10 | 否 | 否 | L | OPEN |
| UI-006 | P3 | UI | ECharts | 控制台出现 2 条容器宽高为 0 的初始化警告 | 否 | 否 | S | OPEN |
| PERF-003 | P3 | 性能 | 前端包 | 主 JS 1,394.53kB，Vite 报 >500kB | 否 | 否 | S | OPEN |
| TEST-003 | P3 | 测试 | 根脚本 | 根 npm test 依赖系统 PATH pytest，当前环境失败 | 否 | 否 | S | OPEN |
| DEPLOY-003 | P3 | 部署 | 运维 | Linux、离线安装、自启动、崩溃恢复、升级回滚未验证 | 否 | 否 | L | OPEN |
| API-006 | P3 | API | OpenAPI | 大量接口没有明确 response model，路径参数命名与规范不一致 | 否 | 否 | M | OPEN |


## SAFE-001 [P0] 暂停、中止和急停不停止 EOL 执行任务

- 分类/模块：安全 / EOL 状态机
- 现象：pause 后步骤从 3 增至 8；abort/emergency 最终均被覆盖为 PASS。
- 影响：操作员无法可靠停止车辆相关检测流程。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/eol_state_machine.json`
- 代码：`backend/app/eol/engine.py:24,54-65; backend/app/api/eol.py:163-195`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：为每个会话持有 task/cancel token；所有步骤前后检查状态；急停先执行安全停车并等待确认。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## SAFE-002 [P0] CAN1/CAN2 断开时一键检测仍 PASS

- 分类/模块：安全 / EOL/联锁
- 现象：审计停止两个通道后启动会话，12 步全部 PASS。
- 影响：可对无反馈车辆生成错误 PASS 结论。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/eol_state_machine.json`
- 代码：`backend/app/eol/engine.py:29-49`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：每步使用 SafetyInterlockService 和关键帧时效；断链立即失败并安全停车。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## SAFE-003 [P0] 高负载积压帧使设备断开后仍被判在线并允许控制

- 分类/模块：安全 / CAN/联锁
- 现象：55Hz profile 停止 5 秒后 CAN2 仍 online，send-once 返回 200。
- 影响：断线车辆可能在错误在线状态下接受控制。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/stale_online_interlock_after_5s.txt`
- 代码：`backend/app/can_gateway/udp_gateway.py:49-53; backend/app/services/lifecycle.py:16-28; backend/app/can_gateway/statistics.py:35-49`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：使用有界队列、接收时间戳而非处理时间、丢弃过期帧；联锁校验 source receive age。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## SAFE-004 [P0] 后端无认证且默认角色为 admin

- 分类/模块：安全/权限 / 认证授权
- 现象：无凭据可进入维护模式；伪造 x-role:admin 删除不存在报告返回 200；OpenAPI 无 security scheme。
- 影响：任何可访问端口的进程可操作控制、维护和删除接口。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/api/security_probe.json`
- 代码：`backend/app/services/app_state.py:8; backend/app/api/config.py:472-475; backend/app/api/reports.py:261-273; backend/app/main.py:12`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：实现认证会话、服务端 RBAC、不可伪造身份和最小权限；控制接口限制本机可信 IPC/令牌。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## SAFE-005 [P0] 急停只停止周期任务并置位，不下发零速/制动帧

- 分类/模块：安全 / 急停
- 现象：接口响应称急停完成，但代码无 safe_stop_command 发送或反馈确认。
- 影响：车辆可能保留最后控制命令，停止周期发送不等于停车。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/simulation/control_loopback_e2e.json`
- 代码：`backend/app/api/control.py:157-169`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：急停采用独立高优先队列，重复发送零速+制动直到反馈确认或超时，并保持锁存。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## EOL-001 [P1] 转向无响应和制动失败 profile 错误 PASS

- 分类/模块：检测 / 故障判定
- 现象：steering_no_response 与 brake_fail 均完成 12 步并生成 PASS。
- 影响：生产可能放行故障底盘。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/simulation/steering_no_response_eol_result.json; evidence/simulation/brake_fail_eol_result.json`
- 代码：`backend/app/eol/engine.py:29-49`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：按 test_plan 执行真实刺激/反馈断言，覆盖转向跟随与制动停止。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## EOL-002 [P1] 低 SOC/告警在第 1 步失败且引擎忽略测试计划

- 分类/模块：检测 / 步骤语义
- 现象：bms_low_soc 和 warning_fault 仅执行 1 步；DEFAULT_STEPS 只提供名称。
- 影响：失败步骤与报告诊断结论错误。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/simulation/bms_low_soc_eol_result.json; evidence/simulation/warning_fault_eol_result.json`
- 代码：`backend/app/eol/engine.py:5,29-49; configs/test_plan.yaml`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：加载计划模型，为每步定义 command、采样窗口、断言和失败策略。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## SAFE-006 [P1] UI 0x121 Byte 预览与实际发送 payload 不一致

- 分类/模块：安全/UI / 手动控制
- 现象：preview 的 bytes_hex 字段排列/0.25 比例与 data、仿真器收到的真实 0.1 比例 payload 不同。
- 影响：操作员看到的待发内容不是实际报文。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/simulation/control_loopback_e2e.json`
- 代码：`backend/app/api/control.py:38-61; backend/app/control/control_121.py:37-52`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：只返回编码器产生的一份 authoritative bytes；字段说明从同一 bytes 解码生成。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## SAFE-007 [P1] 联锁展示接口固定显示允许发送

- 分类/模块：安全/UI / 手动控制
- 现象：interlock-status 不调用 SafetyInterlockService，control/status 仅检查急停。
- 影响：UI 可在实际禁止时显示允许，误导操作员。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/api/get__control__interlock-status.json`
- 代码：`backend/app/api/control.py:65-79,95-112`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：两个状态接口直接返回 SafetyInterlockService.evaluate 结果和阻断原因。
- 工作量/依赖：S / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## SAFE-008 [P1] 安全停车仅发送一次且不验证车辆停止

- 分类/模块：安全 / 安全停车
- 现象：stop scheduler 后只 send_once safe_stop_command。
- 影响：UDP 丢包或反馈异常时无法保证停车。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/simulation/control_loopback_e2e.json`
- 代码：`backend/app/api/control.py:147-155; backend/app/control/safe_stop.py:3-4`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：实现超时状态机、周期重发、速度/制动反馈断言和审计。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## PERF-001 [P1] 目标约 1045fps 时实际仅处理 345.9fps并形成长尾积压

- 分类/模块：性能 / CAN 接收
- 现象：60 秒后模拟器停止，日志继续增长且在线状态延迟。
- 影响：实时性和安全超时失真，长时间运行会耗尽资源。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/stress_1000fps_60s_summary.json; evidence/tests/post_stress_backlog_summary.txt`
- 代码：`backend/app/can_gateway/udp_gateway.py:49-53; backend/app/services/lifecycle.py:16-28`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：引入有界队列、批处理日志、主题节流和负载丢弃策略。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## API-001 [P1] 每帧顺序广播 7 个大 topic，前端每次 timeseries 又发 HTTP

- 分类/模块：API/WebSocket / 实时推送
- 现象：3 秒收到 5,292 消息；7 个主要 topic 各 744 条。
- 影响：网络/CPU 被放大，导致积压与页面抖动。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/api/websocket_probe.json`
- 代码：`backend/app/services/lifecycle.py:16-28; desktop/src/stores/signals.ts:75-80`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：按规范节流：raw 可选、signals 10Hz、statistics 1Hz；timeseries 直接消费 payload。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：是；车辆安全：否


## DB-001 [P1] EOL/CAN/信号/告警/报告核心表均为 0 行

- 分类/模块：数据 / 持久化
- 现象：运行五个 profile 和控制联调后，只有 operator_actions/config_history 有数据。
- 影响：历史追溯、报告关联和审计结论不可依赖。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/database_audit.json`
- 代码：`backend/app/eol/engine.py; backend/app/services/lifecycle.py; backend/app/reports/generator.py`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：建立 session UoW，落库 steps/assertions/frames/signals/alarms/reports，并增加回滚测试。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：是；车辆安全：否


## REPORT-001 [P1] 生成的 DOCX 中文乱码，PDF 中文方块且仅含会话/结果

- 分类/模块：报告 / 生成器
- 现象：PASS/FAIL 文件可打开但内容不可用，且缺 software/DBC/config 版本。
- 影响：报告无法交付生产或审计。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/report_validation.json; evidence/screenshots/current/generated_normal_pass_report_page1.png`
- 代码：`backend/app/reports/generator.py:10-39`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：统一 UTF-8 源文本和嵌入中文字体，按模板写完整步骤/断言/版本并回归渲染。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：是；车辆安全：否


## DEPLOY-001 [P1] electron:build 只执行 Vite，main.cjs 生产仍加载 5173且不拉起后端

- 分类/模块：部署 / Electron
- 现象：没有 installer、Python runtime、dist load、健康等待或进程托管。
- 影响：离线工控机无法按生产方式启动。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/commands/electron_runtime_probe.json; evidence/tests/electron_build_exit.txt`
- 代码：`desktop/package.json:7-13; desktop/electron/main.cjs:21`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：引入 electron-builder/forge，生产 loadFile(dist)，打包/拉起后端并管理生命周期。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：是；车辆安全：否


## SIM-001 [P1] 默认发送地址是 [REDACTED_CAN1_GATEWAY]/99:1234，与仿真器 127.0.0.1:12341/2 不匹配

- 分类/模块：仿真 / 开发配置
- 现象：接收绑定失败会回退 loopback，但发送地址不会同步回退。
- 影响：默认开发命令无法完成双向控制联调，且可能向真实网段发包。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/simulation/loopback_stack_startup.txt; evidence/simulation/channels.dev.audit.yaml`
- 代码：`configs/channels.yaml; backend/app/can_gateway/udp_gateway.py:29-44,59-65`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：明确 dev/production profile，仿真启动必须显式加载 loopback 配置并阻止生产 IP。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## DB-002 [P1] 所有帧同步追加到单个 raw_can_current.csv，无轮转/容量上限

- 分类/模块：日志 / 原始 CAN
- 现象：审计时文件约 119MB；每帧 open/write/close。
- 影响：高帧率下阻塞事件循环并可能耗尽磁盘。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/database_audit.json`
- 代码：`backend/app/storage/raw_log_writer.py:8-16`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：异步批量 writer、按会话/大小轮转、压缩、保留策略和磁盘阈值。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：是；车辆安全：否


## DBC-001 [P2] UDP 半包跨数据报拼接且没有重同步

- 分类/模块：协议 / USR-CAN115
- 现象：5 字节截断包与下一完整包拼出 parse_status=ok 的伪 0x121，真实 0x77 丢失。
- 影响：错误帧可能进入信号与告警逻辑。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/protocol_probe.json`
- 代码：`backend/app/can_gateway/usr_can115.py:57-64; backend/app/can_gateway/udp_gateway.py:47-53`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：UDP 按 datagram 校验 13*n；非法长度整包拒绝。TCP 才使用带同步策略的 stream buffer。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：是；车辆安全：是


## CAN-001 [P2] fps 使用启动以来累计平均而非滚动窗口

- 分类/模块：CAN / 统计
- 现象：压力结束显示 34.7/66.4fps，而 60 秒区间处理总量约 345.9fps。
- 影响：UI、超时和容量判断失真。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/stress_1000fps_60s_summary.json`
- 代码：`backend/app/can_gateway/statistics.py:35-49`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：使用 1s/5s 滚动窗口和单调时钟。
- 工作量/依赖：S / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## CAN-002 [P2] recent_frames 仅 2,000 帧，低于资料包每通道至少 10,000 建议

- 分类/模块：CAN / 缓存
- 现象：约 1000fps 时只保留约 2 秒且两通道共享。
- 影响：诊断回看与短时统计不足。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/protocol_probe.json`
- 代码：`backend/app/can_gateway/manager.py:12`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：按通道有界环形缓存，容量配置化并监控使用率。
- 工作量/依赖：S / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## DBC-002 [P2] 运行解码只产生总 bitmap，监控详情中的保护位为固定数据

- 分类/模块：DBC / 0x102
- 现象：protocol probe 只得到 BMS_Protect_Bitmap=32769。
- 影响：实际单项保护状态可能与 UI 不一致。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/protocol_probe.json`
- 代码：`backend/app/dbc/service.py:89-91; backend/app/api/can.py:256-267`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：按 override 显式输出 unsigned bool/bitmap 信号，并用当前帧值构造详情。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：是


## API-002 [P2] 大量固定数据返回 200 且未统一标识 Mock

- 分类/模块：API / Dashboard
- 现象：统计、历史、曲线等可看似真实；只有部分 dashboard 有 mock 字段。
- 影响：操作员可能把演示数据当生产事实。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/api/api_probe_summary.json`
- 代码：`backend/app/api/can.py:13-31,178-212; backend/app/api/eol.py:18-133`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：字段级 source/quality/mock 元数据；生产模式禁止无标识 fallback。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：是


## API-003 [P2] 错误响应结构和 trace_id 不统一

- 分类/模块：API / 错误处理
- 现象：HTTPException 使用 detail，通用 handler 使用平铺结构且 trace_id 可空。
- 影响：前端无法稳定展示原因，审计链路断裂。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/api/security_probe.json`
- 代码：`backend/app/main.py:15-18; backend/app/api/config.py:472-475`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：统一异常基类、中间件生成 trace_id、结构化错误和日志关联。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## API-004 [P2] 接口允许 TCP 但运行时不存在 TCP gateway

- 分类/模块：API/CAN / 协议配置
- 现象：保存 TCP 后仍由 UdpCanGateway 运行。
- 影响：配置与实际行为不一致。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/api/get__config.json`
- 代码：`backend/app/api/config.py:319-344; backend/app/can_gateway/manager.py:13`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：实现 TcpCanGateway 或拒绝 TCP 并明确未支持。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## API-005 [P2] 前端 DELETE 不发送 x-role，后端又把不存在 ID 回退为 Mock 报告

- 分类/模块：API/权限 / 报告删除
- 现象：正常 UI 删除恒 403；伪造 admin 对不存在 ID 返回成功。
- 影响：用户流程不可用且接口语义危险。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/api/security_probe.json`
- 代码：`desktop/src/api/http.ts:21-25; backend/app/api/reports.py:125-126,261-273`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：依赖认证上下文；不存在返回 404；前端不自行声明角色。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## UI-001 [P2] 1366×768 多页裁切或需页面滚动

- 分类/模块：UI / 响应式
- 现象：overview/network/curve/manual/auto/alarm 裁切，report/history/settings 使用页面内部滚动。
- 影响：兼容分辨率下关键按钮和状态不可见。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/screenshots/current/ui_runtime_metrics.json`
- 代码：`desktop/src/pages/*.vue; desktop/src/components/layout/AppShell.vue:22`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：建立 1366 专用压缩网格，页级 overflow hidden，仅表格内部滚动。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## UI-002 [P2] 页面主体收到实时数据时顶部 CAN1/CAN2 仍可显示 offline

- 分类/模块：UI / 顶部状态
- 现象：新开页截图中状态栏与 CAN 表/仿真状态不一致。
- 影响：操作员无法判断真实链路。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/screenshots/current/03_can_monitor_1920x1080.png`
- 代码：`desktop/src/stores/appStatus.ts:18-58; desktop/src/components/layout/TopStatusBar.vue:41-47`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：以单一 channel store 为真源，先加载状态并定义 loading，不用 fallback offline 覆盖。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：是


## UI-003 [P2] 显示 0/256 已选择但六图仍有所有曲线

- 分类/模块：UI / 实时曲线
- 现象：checkbox 与 series 没有真实绑定。
- 影响：用户无法控制监控负载和曲线内容。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/screenshots/current/05_realtime_curve_1920x1080.png`
- 代码：`desktop/src/pages/RealtimeCurvePage.vue`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：按 selected signal 过滤 series，保存选择并增加交互测试。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## UI-004 [P2] 存在 4 个白底原生输入控件

- 分类/模块：UI / 手动控制
- 现象：运行时 computed style 审计检出。
- 影响：破坏工业主题并降低暗环境可读性。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/screenshots/current/ui_runtime_metrics.json`
- 代码：`desktop/src/pages/ManualControlPage.vue`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：统一 IndustrialInput/Range 控件和 focus/disabled 样式。
- 工作量/依赖：S / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## PERF-002 [P2] WsClient 无 close/error/reconnect/off，页面 handler 不注销

- 分类/模块：前端 / WebSocket 生命周期
- 现象：路由切换会累积 callbacks；connect 可重复创建 socket。
- 影响：长时间页面切换后重复请求和内存增长。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/commands/search_websocket.txt`
- 代码：`desktop/src/api/websocket.ts:1-15; desktop/src/pages/AutoTestPage.vue:333-343`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：实现单例连接状态机、指数退避、unsubscribe/off 和组件 scope cleanup。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## DB-003 [P2] SignalLogWriter.write 是空函数

- 分类/模块：日志 / 解码信号
- 现象：无解析后信号 CSV/Parquet 落盘。
- 影响：历史曲线和追溯数据缺失。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/database_audit.json`
- 代码：`backend/app/storage/signal_log_writer.py:1-3`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：实现批量信号日志和质量/会话字段。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：是；车辆安全：否


## DB-004 [P2] 每条 execute 立即 commit，无会话事务/回滚；shutdown 未 close 数据库

- 分类/模块：数据库 / 事务
- 现象：步骤、断言和报告无法原子保存。
- 影响：部分失败可留下不一致记录并泄漏句柄。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/database_audit.json`
- 代码：`backend/app/storage/database.py:8-31; backend/app/services/lifecycle.py:48-52`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：增加 transaction context、FK 检查、busy retry 和 shutdown close。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## TEST-001 [P2] 从项目根执行 pytest simulator/tests 收集失败

- 分类/模块：测试 / 仿真器
- 现象：ModuleNotFoundError: can_frame_simulator；切入 simulator 目录后 1 条通过。
- 影响：README 推荐命令不可复现。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/simulator_pytest.txt`
- 代码：`simulator/tests/test_profiles.py; simulator/pyproject.toml`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：安装 simulator 包或配置 pythonpath，CI 从根执行。
- 工作量/依赖：S / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## TEST-002 [P2] 无 npm test、lint，后端未安装 pytest-cov

- 分类/模块：测试 / 前端/覆盖率
- 现象：只能证明类型检查和构建，无法证明交互。
- 影响：回归风险高，关键 UI 与 WebSocket 无自动测试。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/frontend_test_attempt.txt; evidence/tests/frontend_lint_attempt.txt; evidence/tests/backend_coverage_attempt.txt`
- 代码：`desktop/package.json; backend/pyproject.toml`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：添加 Vitest、ESLint、Playwright/Electron E2E 和覆盖率门槛。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## DEPLOY-002 [P2] npm audit 报 2 high + 2 moderate

- 分类/模块：依赖 / npm
- 现象：Electron 31、Vite/esbuild/ECharts 依赖链有已知问题。
- 影响：扩大桌面端攻击面。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/npm_audit.json`
- 代码：`desktop/package.json`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：升级受支持 Electron/Vite/ECharts，验证兼容并纳入依赖扫描。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## REPORT-002 [P2] 预览面板不读取真实 DOCX/PDF

- 分类/模块：报告/UI / 预览
- 现象：任意行均显示固定 12 页模板元数据。
- 影响：无法核对生成文件，JSON/CSV tab 也不是真实内容。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/screenshots/current/09_report_management_1920x1080.png`
- 代码：`backend/app/api/reports.py:125-145; desktop/src/pages/ReportManagementPage.vue`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：提供安全的 PDF 渲染/文本摘要 endpoint，并按真实文件类型预览。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## UI-005 [P3] 10 页像素差异仍为 28.7%~40.0% 像素超过阈值 10

- 分类/模块：UI / 视觉还原
- 现象：报告、一键检测和总览的比例/密度偏差最明显。
- 影响：影响视觉一致性但不直接改变业务。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/screenshots/diff/visual_diff_metrics.csv`
- 代码：`desktop/src/pages/*.vue`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：按参考图逐页校准网格、字号、卡片高度和图表比例。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## UI-006 [P3] 控制台出现 2 条容器宽高为 0 的初始化警告

- 分类/模块：UI / ECharts
- 现象：图表在首次布局时初始化早于容器尺寸。
- 影响：偶发空图或首次 resize 闪烁。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/screenshots/current/browser_console_warnings.json`
- 代码：`desktop/src/components/charts/*.vue`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：使用 ResizeObserver 和非零尺寸后 init。
- 工作量/依赖：S / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## PERF-003 [P3] 主 JS 1,394.53kB，Vite 报 >500kB

- 分类/模块：性能 / 前端包
- 现象：11 页全部同步导入且 ECharts 未拆包。
- 影响：首屏和升级包体积偏大。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/frontend_build.txt`
- 代码：`desktop/src/router/index.ts; desktop/vite.config.ts`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：路由懒加载并拆分 ECharts/vendor。
- 工作量/依赖：S / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## TEST-003 [P3] 根 npm test 依赖系统 PATH pytest，当前环境失败

- 分类/模块：测试 / 根脚本
- 现象：新环境无法一键测试。
- 影响：影响审计/CI 可复现性。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/tests/root_npm_test.txt`
- 代码：`package.json`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：显式调用 backend/.venv 或统一 uv run。
- 工作量/依赖：S / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## DEPLOY-003 [P3] Linux、离线安装、自启动、崩溃恢复、升级回滚未验证

- 分类/模块：部署 / 运维
- 现象：当前只有 Windows 开发运行证据。
- 影响：部署风险未知。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/commands/os_version.txt`
- 代码：`docs/17_deployment_plan.md; desktop/package.json`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：建立 Windows 工控机安装/升级演练和 Linux 后端 CI。
- 工作量/依赖：L / 无
- 状态：OPEN；阻止生产：否；车辆安全：否


## API-006 [P3] 大量接口没有明确 response model，路径参数命名与规范不一致

- 分类/模块：API / OpenAPI
- 现象：OpenAPI 112 路由可枚举，但契约约束弱。
- 影响：客户端类型和错误契约易漂移。
- 复现：按证据文件中的命令或脚本执行并对比记录字段。
- 证据：`evidence/api/api_spec_comparison.json`
- 代码：`backend/app/api/*.py`
- 原因：实现停留在演示/最小闭环，缺少生产约束。
- 建议：为公共 API 添加 request/response Pydantic 模型并做契约测试。
- 工作量/依赖：M / 无
- 状态：OPEN；阻止生产：否；车辆安全：否
