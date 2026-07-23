# 生产身份、路由守卫与首次初始化

## 2026-07-23 安全操作审计补充

安全拒绝、控制 intent/result、safe-stop/emergency/release、override 申请/批准/撤销、EOL 创建和危险状态变更均采用必需审计。必需审计不可写会锁存存储故障并返回 503；普通只读偏好仍可采用降级审计。日志与证据不得保存 bootstrap secret、session token、配置签名键或 hardware acceptance 信任根。

hardware acceptance 要求申请人与两名批准人共三人互异。此职责分离是生产运动门禁，不是普通 RBAC 或 override 可以替代的权限。

更新日期：2026-07-22。

## 方案与边界

平台采用后端本地账户库和短期随机 session，适合单机工控软件且不依赖云身份服务。后端是唯一权限真源；Vue 菜单、按钮和路由守卫根据 `/auth/me` principal 提供操作引导，但不能代替 API 的 401/403。

默认 session 有效期 900 秒，可在 60..28800 秒内配置。密码为 12..128 位且至少满足四类字符中的三类；使用随机 salt + scrypt。连续失败默认 5 次后锁定 300 秒。锁屏撤销原 session，正确密码解锁后得到新 session；登出、管理员撤销和绝对过期都是终态。

前端包含 `/login`、`/lock`、`/forbidden`。业务路由声明 `requiresAuth` 和 `roles`；直接访问无权路由跳 403。401 或 WebSocket 4401 会清除 renderer session、停止 WebSocket 重连并引导重新登录。token 只放在当前窗口的 sessionStorage；刷新可恢复并用 `/me` 重验，Electron 重启不恢复。

## 路由角色

- viewer：总览、CAN 监控、信号、曲线、告警、报告、历史。
- operator：viewer + 一键检测。
- engineer：operator + 手动控制、网络配置、系统设置。
- admin：全部页面和账户、配置包、维护等管理员按钮。

API 精确角色见 `api-authorization-matrix.csv`。例如 engineer 页面显示“保存普通设置”，但签名包导入/应用、通道重配置、危险维护和恢复默认按钮只对 admin 显示，后端仍再次校验。

## 干净机首次安全初始化

1. 使用专用 Windows 服务账户安装程序，为 `C:\ProgramData\ChassisEOL` 设置仅服务账户和批准管理员可读写的 ACL；不要使用仓库 `data/` 作为 production 数据目录。
2. 从本机秘密存储注入随机 `CHASSIS_CONFIG_SIGNING_KEY`（至少 32 字符）。不要写入 `.env`、脚本、命令历史或版本库。
3. 复制 `configs/production-config.template.json` 到仓库外，填写批准网卡、CAN endpoint/source allowlist、车型、完整 DBC hash、方案、路径、工位和打印机。保留后端 `CHASSIS_BACKEND_HOST=127.0.0.1`。
4. 使用 `scripts/sign_configuration.py` 生成 `C:\ProgramData\ChassisEOL\config\active-package.json`；用 `python scripts/generate_api_docs.py` 只生成文档，不参与签名。
5. 设置 `CHASSIS_RUNTIME_PROFILE=production`、`CHASSIS_DATA_DIR`、`CHASSIS_ACTIVE_CONFIG_PATH`、host/port 后启动服务。缺少签名包或签名不符必须启动失败。
6. 若账户库为空，从 `C:\ProgramData\ChassisEOL\auth\bootstrap-admin.secret` 读取一次性 secret。在仅本机可见的登录页建立首个 admin 强密码。完成后确认文件已自动删除；不要截图或复制到工单。
7. admin 建立具名 operator/engineer/viewer 账号；不得共享 admin。锁屏、登录失败限制、注销和会话撤销各验证一次。
8. admin 在系统设置页先导入相同签名包执行 dry-run，复核 diff、DBC、端口、data root、数据库和控制空闲检查；仅在批准变更窗口输入原因并 APPLY。
9. production 应用会等待批准来源帧；未收到则回滚。首次接真实网络前仍应按“只监听、禁主动运动帧”台架方案验证，不因软件检查通过而连接可运动执行器。

也可在首次进程启动前临时注入随机 `CHASSIS_BOOTSTRAP_SECRET`；仅建议自动化部署使用，初始化完成立即从服务环境移除。日志不得包含该值。

## 威胁模型简表

| 资产 | 攻击者/故障 | 信任边界 | 主要缓解 | 残余风险 |
|---|---|---|---|---|
| 车辆运动控制 | 本机低权限用户、被劫持 renderer、误操作 | Vue/Electron → FastAPI → SafetyInterlock → CAN | 后端 RBAC、短 session、0x121 白名单、安全联锁、审计、localhost | 本机管理员或系统账户失陷仍可控制软件；物理安全链待验证 |
| 账户和 session | 暴力猜测、token 窃取、共享账号 | 登录 API、sessionStorage、SQLite | scrypt、失败锁定、token 摘要、短期/撤销/锁屏、无 build token | renderer/XSS 可读取当前 session；需 CSP、安装签名和 OS 加固 |
| 生产配置/DBC 身份 | 篡改 endpoint/hash/路径、回滚旧配置 | 离线配置 → 签名工具 → active package | 严格 schema、HMAC、profile、diff、admin、健康检查、回滚、审计 | HMAC 是本机共享秘密；密钥轮换和硬件保护尚未实现 |
| CAN 反馈 | UDP 源伪造、陈旧/非法帧 | NIC/USR-CAN115 → gateway/cache | 精确 IP+端口 allowlist、质量/范围/时效校验、未授权源不更新在线状态 | 同网段源欺骗及真实设备源端口行为需硬件/网络隔离确认 |
| 生产数据/报告 | 越权读取、路径穿越、磁盘/DB 故障 | API、SQLite、文件系统、Electron shell | 敏感读需会话、文件根限制、DB 不可写 fail-closed、审计 | 备份恢复、磁盘满、打印机和数据根统一仍属于后续工作 |

## 必须继续完成的硬件/运维工作

- 真实 USR-CAN115 只监听、源端口稳定性、TCP 断线重连和网络隔离验证。
- 物理急停、安全 PLC/继电器、底盘看门狗和 safe-stop 保持策略审批。
- Windows 服务账户、ACL、秘密存储/轮换、安装包签名、CSP 和主机加固。
- production DBC/车型/方案/endpoint/打印机现场审批以及干净机安装演练。
