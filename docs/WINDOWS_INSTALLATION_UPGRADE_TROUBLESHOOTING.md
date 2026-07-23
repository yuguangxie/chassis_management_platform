# Windows 安装、升级与排障

## 2026-07-23 RC 验证矩阵

CI 安装验证使用中文和空格临时路径，并临时占用 8800 证明 sidecar 会选择动态 localhost 端口；运行时 PATH 移除 Node/Python/uv，且不依赖互联网。验证首次/二次启动、11 页、simulator 缺失时 offline 与控制 409、sidecar 一次崩溃后的有界恢复、sidecar 缺失诊断、卸载后业务数据保留。旧版本升级/失败回滚、普通用户与管理员独立 VM、特定防火墙/AV 厂商仍须在目标镜像上补证，不能由本地 Mock 结果替代。

## 安装

1. 先核对 `release-manifest.json` 中 installer 文件名和 SHA-256。
2. 正式生产只接受 Windows 显示有效签名且 manifest `formal_release=true` 的包；`unsigned-internal` 只能用于内测。
3. 默认执行普通用户 per-user 安装；只有组织的软件分发策略要求时才批准提升权限。安装路径支持中文和空格。
4. 首次启动保持 Mock。诊断页消失并出现登录页，只表示本地后端 ready，不表示车辆可控。
5. 从 `<userData>/data/auth/bootstrap-admin.secret` 获取一次性管理员初始化值，完成初始化后该文件自动删除。不要截图、复制到工单或写入日志。
6. 建立 operator/engineer/admin 账户后，按角色做一次登录、锁屏、登出和 session 过期演练。

## 切换 production

由管理员在 Windows 安全配置/进程启动环境中提供 `CHASSIS_DESKTOP_RUNTIME_PROFILE=production`、签名 active configuration 路径和配置验签 key。它们不得写入安装包或 Vite 变量。production 初始化会重新校验批准车型、完整 DBC hash、报告依赖、data_root 和打印机；任一条件不确定时停留在诊断页并 fail-closed。

在真实车辆接入前仍必须完成现场网卡、USR-CAN115、物理急停、安全 PLC/继电器、safe-stop 保持策略和白名单抓包确认。

## 升级、migration 与回滚

- 同一 `appId` 的 NSIS 包执行就地应用升级；业务 data_root 不在安装目录中。
- sidecar 每次启动运行版本化 migration。旧库 migration 前先做在线一致性备份，失败则事务回滚并保留备份，应用停在诊断页，不报告启动成功。
- 新版程序拒绝打开高于自身支持版本的数据库，因此禁止“直接安装旧 exe 后继续使用已升级库”。
- 应用二进制回滚必须同时选择兼容的 migration 备份：先保留当前库和审计，再恢复升级前备份到隔离位置完成完整性检查，最后由管理员显式切换。不要覆盖唯一副本。
- 发布流水线可通过 `verify_windows_installer.ps1 -PreviousInstallerPath <旧包>` 接入批准的历史 fixture；当前仓库没有可信旧安装包，因此该矩阵项不能伪造为已验证。

## 卸载与数据导出

卸载器默认保留数据库、日志、报告、导出、备份和审计。卸载前管理员可在系统设置创建备份并导出到批准介质。卸载应用不等于删除业务数据；后续删除必须经过 retention/cleanup dry-run、确认和审计。

## 常见故障

| 现象 | 安全状态 | 处理 |
|---|---|---|
| 一直显示启动诊断 | 车辆 offline、发送停止 | 查看 `<data_root>/logs/sidecar/sidecar.log` 和 `runtime-state.json`；检查资源是否被杀毒隔离、data_root 权限/空间。 |
| 端口占用 | 自动改用其他 localhost 端口 | 不开放防火墙公网规则；确认没有策略阻止随机回环端口。 |
| sidecar 连续崩溃 | 3 次后停止重启 | 保存日志、release manifest 和 Windows Event Viewer 信息；不要尝试手工发送 CAN。 |
| 防火墙/杀毒拦截 | readiness 失败 | 只对已验证 hash/签名的安装目录做最小 allowlist；不得关闭整机防护。 |
| simulator 未运行 | 页面显示 CAN offline，控制 409 | 这是安装包默认的正确状态。 |
| DBC/config 不匹配 | production 启动或控制被拒绝 | 重新获取已批准签名配置，不允许改 hash 绕过。 |
| PDF/预览不可用 | 报告能力明确报错 | 运行打包依赖检查；不得把 DOCX 改后缀伪装 PDF。 |
| 数据库版本过新 | 旧版本拒绝启动 | 使用兼容新版，或按备份恢复流程回滚数据库。 |

排障材料不得包含账户密码、bootstrap secret、session token、sidecar credential 或配置签名 key。
