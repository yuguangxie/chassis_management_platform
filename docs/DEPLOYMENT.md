# 生产部署与数据目录检查

## 2026-07-23 Windows RC 供应链门禁

RC 必须从 clean commit 构建，release manifest 记录 commit、dirty=false、构建时间、签名状态、数据库 schema、DBC/schema hash、安全边界及所有 artifact SHA-256，同时生成 CycloneDX SBOM、npm/pip audit。无 Authenticode 证书只能输出文件名明确包含 `unsigned-internal` 的内测包，不能标为 production candidate；受保护证书存在时才运行 workflow 的 `signed-production-candidate-windows-installer` job 并要求时间戳/Windows 验签有效。

安装运行仍使用 localhost 动态端口、每次启动短期 sidecar credential、最小 preload、`nodeIntegration=false`、`contextIsolation/sandbox/webSecurity=true`、单实例、有界重启与优雅退出。首次启动默认 Mock/回环，不自动启动 simulator，不连接现场 endpoint，不发送 CAN。

## 干净机准备

1. 使用受限 Windows 服务账户创建站点数据目录，例如由安装器选择的本地固定磁盘目录；不要把路径或账号提交到仓库。
2. 仅授予服务账户和获批管理员访问权限，普通操作员不应有资源管理器删除权限。
3. 在本机秘密存储中设置配置签名 key，生成并签署 production configuration；`data_root` 必须是该站点批准路径。
4. 设置 `CHASSIS_RUNTIME_PROFILE=production`、`CHASSIS_ACTIVE_CONFIG_PATH`、`CHASSIS_MIN_FREE_BYTES` 和 `CHASSIS_PRINT_BACKEND=windows`。
5. 安装 backend production extra，运行 `scripts/check_report_dependencies.py`。
6. 首次启动前确认数据盘剩余空间、备份介质和 Windows 打印机驱动。
7. 启动后用管理员 session 查询 `/storage/stats`、`/storage/schema-version`、`/reports/capabilities`，再创建并验证首个备份。

## 启动参数

开发模板只监听 `127.0.0.1`，打印 backend 为 virtual。production 仍默认仅监听 localhost；现场不得通过修改前端静态资源注入 token、路径或秘密。

`CHASSIS_DATA_DIR` 是未加载 signed package 前的引导默认值；production 业务数据的最终真源是签名包中的 `data_root`。active package 路径本身应由安装器/服务参数显式指定，避免引导路径歧义。

## 上线前演练

- 对旧 schema 的副本逐版本升级并核对 migration backup；
- 创建备份、篡改副本确认拒绝、恢复到隔离工控机；
- 使用受控小分区演练磁盘阈值和只读 ACL；
- 用批准的虚拟打印机和最终物理打印机分别验证 job id 与纸面结果；
- 所有演练期间禁止连接可运动 CAN 设备。

## Windows 安装包

Windows x64 使用 Electron Builder + NSIS，默认 per-user 安装，卸载保留业务 data_root。首次安装只启动 Mock/localhost sidecar，不启动 simulator 或发送 CAN。安装、升级、数据导出与排障步骤见 `WINDOWS_INSTALLATION_UPGRADE_TROUBLESHOOTING.md`，构建和签名门槛见 `DESKTOP_PACKAGING.md`。

正式投产必须同时满足：有效 Authenticode、release manifest `formal_release=true`、干净源码构建、独立普通用户干净机通过、批准历史版本升级/回滚通过、企业防火墙/杀毒 allowlist 通过。当前 `unsigned-internal` 包只允许回环内测。
