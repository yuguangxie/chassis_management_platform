# 软件 P0/P1 收口与 Windows RC 验证索引

> 工作包日期：2026-07-23  
> 初始 HEAD：`ba47b0aaebc62eae3131d23ed9d318fdb4721130`  
> 初始工作树：dirty，包含此前尚未提交的 UI 一致性收口和 2026-07-23 完整审计；这些修改已逐项保留并纳入本工作包。  
> 验证边界：仅临时 `data_root`、Mock、虚拟打印和 `127.0.0.1`；`nonLoopbackRequests=0`。未访问真实 CAN、车辆、打印机或非回环 endpoint，未执行 HIL 或运动测试。

## 1. 交付定位

本工作包关闭审计中的可由仓库软件实现和自动验证的 P0/P1，并把候选版本推进到“真实 CAN 只监听验收前的软件 RC”。它不把真实车辆状态标记为 READY。正式生产运动仍同时要求：正式签名且 clean 的 release、签名 production config、匹配的独立 hardware acceptance artifact、完整安全反馈、可写 DB/审计、无急停/严重告警/队列故障，以及后续现场物理验收。

## 2. 追踪入口

- [`00_IMPLEMENTATION_MATRIX.md`](00_IMPLEMENTATION_MATRIX.md)：问题 → 文件/行号 → API/schema → 测试 → 文档。
- `backend/tests/test_20260723_p0p1_closure.py`：production 配置、intent/outbox、hardware artifact、EOL identity、adapter/TCP 和元数据真实性的集中故障注入。
- `backend/tests/test_data_lifecycle.py`：migration/backup/restore/retention/rotation/compression/打印的生命周期测试。
- `docs/openapi.json` 与 `docs/api-authorization-matrix.csv`：从当前应用模型重新生成的 151 个 API operation 与角色矩阵。
- 本目录下的 `e2e/`、`release/`、`clean-machine/`、`ci-runtime/` 均为运行生成证据目录；不得在其中保存 bootstrap secret、session token、签名 key、账号、现场 IP 或用户数据。

## 3. 软件安全结论

| 门禁 | 当前实现 |
|---|---|
| production 配置权威 | 普通 config/channel update/restore 全部 `409 SIGNED_CONFIG_REQUIRED` 且审计；唯一入口为签名包 import/dry-run/diff/admin confirm/apply/health/rollback |
| 主动发送边界 | CAN1 永久锁定；只允许 CAN2 `0x121`；0x123/0x126/0x710/0x715/NMT 禁用 |
| 控制可靠审计 | schema v4 `control_intents`；前写失败零 TX，后写失败锁存/停周期/受限补偿，重启终结未决 intent |
| 硬件验收授权 | 独立签名 artifact、三人职责分离、UTC 有效期/撤销、工位/车型/release/config/DBC/plan hash 全匹配；UI 只读 |
| 网络与 transport | production UDP-only；签名 adapter name/index/MAC/bind IP 漂移阻断；非批准 UDP source 不更新 online/cache |
| EOL 追溯 | 无 demo 默认；operator/principal 与 station/config 后端覆盖；VIN/底盘/序列/车型/工单/plan 校验及重复策略；session identity 全链路 |
| 运行元数据 | release manifest、config/plan/DBC 使用真实来源；不可用时 null/0/未知，不使用固定伪值 |
| 日志与 retention | 大小+时间轮转、gzip、有界保留、严格 schema；各数据类别 preview/job/保护/取消/失败恢复；production Parquet 禁用 |

## 4. 本地验证结果

以下结果来自最终源码提交及其 Windows release 构建；全部动态验证仅使用 Mock、临时数据目录和回环地址。

| 命令 | 结果 |
|---|---|
| `backend\.venv\Scripts\python.exe scripts\run_quality.py --suite all --coverage` | PASS：219 backend + 3 simulator；backend 78.52%，simulator 42.98% |
| `npm.cmd run lint` | PASS |
| `npm.cmd run test` | PASS：21 files / 144 tests；statements 56.50%、branches 58.36%、functions 67.05%、lines 58.54% |
| `npm.cmd run typecheck` | PASS |
| `npm.cmd run build` | PASS：2271 modules |
| `npm.cmd run test:bundle` | PASS：main gzip 23,659 B；ECharts gzip 367,892 B；total JS gzip 520,643 B |
| `npm.cmd run test:sidecar` | PASS：4 tests |
| `npm.cmd run test:e2e` | PASS：11 页 × 2 分辨率、22 张截图；60/60 信号样本为 `good`，主要按钮节点/状态稳定，offline control=409，`nonLoopbackRequests=0` |
| `npm.cmd run test:e2e:verify` | PASS：Electron v43.1.0、22 张截图、11 页交互、offline control=409 |
| `npm.cmd audit --audit-level=high` | PASS：596 个依赖，0 个已知漏洞 |
| `python -m pip_audit --skip-editable` | PASS：0 个已知漏洞；本地 editable 项目自身不属于第三方漏洞库扫描对象 |
| `scripts/check_report_dependencies.py` | PASS：ReportLab 原生 PDF、python-docx、PDF 预览可用；DOCX 与 PDF 独立渲染，未启用外部 DOCX→PDF 转换器 |
| Windows NSIS / installed-package | PASS：clean commit 构建、中文与空格路径、8800 端口占用、11 页 × 2 分辨率；22 张截图路由/尺寸匹配且哈希全部唯一；二次启动、有界崩溃恢复、启动失败诊断、卸载保留数据 |
| GitHub Actions `29997457365` | PASS：`quality`、两轮 `renderer-e2e`、`unsigned-internal-windows-installer`；[运行记录](https://github.com/yuguangxie/chassis_management_platform/actions/runs/29997457365) |

## 5. Windows release candidate

| 项目 | 证据 |
|---|---|
| 源码 commit | `40dc553ea4155507df9f9d3b69718b2b816fd687` |
| 源码状态 | `dirty=false`，`dirty_file_count=0`；构建前冻结，finalize 校验 commit 未变化 |
| 安装包 | `Chassis-EOL-Setup-1.0.2-unsigned-internal-x64.exe`，165,173,758 bytes |
| 安装包 SHA-256 | `9ae15624cd9cbff122b2c4d37ec7b559c87e3123b4f822dccac570a74201fdb6` |
| 签名状态 | `signed=false`、`formal_release=false`、`release_label=unsigned-internal`；不得作为正式生产签名包 |
| 供应链证据 | `release/sbom.cdx.json`、`npm-audit.json`、`pip-audit.json`、`signing-status.json`、`release-manifest.json` |
| 安装后证据 | `clean-machine/clean-machine-matrix.json` 与 22 张 installed-package 页面截图；`passed=true`、`route_capture_matches=true`、`viewport_matches_request=true`、`unique_page_captures=true` |
| CI 证据 | `ci-final.json`；source commit 与 release manifest 一致；正式签名 job 因无证书输入按设计跳过 |
| 未执行矩阵项 | 无历史安装包，故升级/回滚未执行；独立普通用户/管理员 VM 和厂商 AV/防火墙仍属外部验收 |

安装包本体位于本机构建目录 `desktop/release/windows/`，因体积与发布介质策略不提交 Git；校验时必须以本节 SHA-256 和 `release/release-manifest.json` 为准。

## 6. 现场仍需确认

- 物理急停、独立安全 PLC/继电器、动力隔离和故障树/FMEA；
- 目标控制器 firmware、watchdog、20 ms 周期抖动、safe-stop 停发/保持/确认语义；
- 各车型/固件批准 DBC、阈值、测试计划、金样/坏样与 GR&R；
- 真实 USR-CAN115 的只监听 source/帧序/丢包/粘包验证；
- 真实打印机、驱动、脱机/卡纸/取消/重试与报告 hash 抽查；
- 目标 IPC 8～24 小时稳态、1000 fps、磁盘/内存/GPU/队列/杀软行为；
- Authenticode 组织证书、受保护 CI secret 与可信时间戳；
- 普通用户/管理员独立 Windows 镜像、旧版本升级/失败回滚、厂商防火墙/AV。

真实 CAN 下一步只能做受控“只监听”：执行器断能、车轮离地、物理急停可达、禁止任何主动发送。只有现场签名 artifact 完成后，才可另行审批静态/封闭低速运动验证。

本次标准 CI 未请求可选的 `1000 fps / 10 min` 长稳态 job；该项以及目标 IPC 的 8～24 小时软件 soak 仍需在后续 nightly/目标机验证中完成。
