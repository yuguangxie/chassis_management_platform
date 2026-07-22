# Windows 桌面产品化与离线打包

更新时间：2026-07-22。

## 方案选择

采用 Electron Builder 26 + NSIS，后端采用 PyInstaller onedir。没有选择 Electron Forge，原因是本项目只需要一个 Windows x64 安装目标，Electron Builder 对 NSIS、`extraResources`、证书环境变量、产物命名和 per-user 卸载策略的配置更直接；Forge 的 maker/plugin 抽象不会增加本项目的安全收益。

PyInstaller onedir 将 Python 3.11 解释器、FastAPI/uvicorn、cantools、SQLite、python-docx、ReportLab、PyMuPDF 和 Windows 打印依赖一并收集。目标机不需要 Node、Python、uv 或互联网。Noto Sans CJK 字体、字体许可证、批准的 DBC、安全默认配置和 production 配置 schema 由 Electron `extraResources` 放入只读安装资源目录。

## 运行结构

```text
Electron main process (single instance)
  -> allocates dynamic 127.0.0.1 TCP port and loopback UDP test range
  -> generates 256-bit per-start sidecar credential
  -> starts resources/backend-sidecar/chassis-eol-backend.exe
  -> polls public minimal /api/v1/health
  -> polls credential-protected /internal/sidecar/readiness
  -> loads app.asar/dist/index.html with hash routing
  -> renderer sends user session + transient sidecar header/protocol
```

sidecar credential 只保存在本次 Electron/renderer 进程内存，不写入静态资源、数据库或日志。它只增加“本机进程边界”，不替代后端账户、短 session 和角色鉴权。HTTP 除最小 health 外要求 `X-Chassis-Sidecar`；WebSocket 要求 `chassis-sidecar.<credential>` 子协议，同时仍要求用户 session 子协议。

## 安全默认值

- 安装包默认 `mock` profile，只绑定 `127.0.0.1`。
- 首次启动不启动 simulator、不连接现场 endpoint、不启动发送调度器。
- CAN2 主动发送白名单仍只有 `0x121`；`0x123`、`0x126`、CANopen NMT 不启用。
- sidecar readiness 只表示本地软件完成初始化，不表示车辆 ready。没有 simulator/反馈时 CAN1/CAN2 为 offline，运动控制返回 409。
- production 必须由外部运行环境显式选择，并继续通过签名 active configuration、车型和完整 DBC hash 校验；包内不含配置签名 key、现场 IP、账号或 token。
- renderer 保持 `nodeIntegration=false`、`contextIsolation=true`、`sandbox=true`；preload 只暴露窗口控制、受 data_root 限制的文件打开和只读运行连接快照。
- 新窗口、任意导航和 Electron 权限请求默认拒绝。

## 资源与数据路径

生产资源从 `process.resourcesPath` 读取；renderer 从打包后的 `app.asar/dist` 读取；业务数据唯一落在 `app.getPath('userData')/data`。不读取源码 cwd。

数据库、日志、原始 CAN、解码信号、报告、导出、临时文件、备份、打印任务和 bootstrap 文件继续由唯一 data_root 推导。卸载默认保留 userData。管理员可在系统设置中先创建一致性备份/导出，再单独按数据治理流程删除。

## sidecar 生命周期

- TCP/UDP 端口先做回环占用检测；端口竞争导致启动失败时按有界策略重启并重新分配。
- stdout/stderr 写入 `<data_root>/logs/sidecar/sidecar.log`，瞬时凭据会在写盘前脱敏。
- 30 秒内未 readiness 切到诊断页；诊断页明确车辆接口离线、发送停止及日志位置。
- 运行中崩溃最多重启 3 次，指数退避；每次重启更换端口和凭据。
- Electron 退出先调用受保护的 shutdown endpoint，让 FastAPI 完成 CAN、遥测、打印和数据库 shutdown hooks；8 秒后才强制终止。

## 构建与签名

```powershell
npm.cmd ci --prefix desktop
uv sync --project backend --locked --extra test --extra quality --extra production --extra packaging
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_windows_release.ps1
```

没有 `CSC_LINK` 时产物名必须包含 `unsigned-internal`，manifest 中 `formal_release=false`。正式候选构建使用 Electron Builder 标准 `CSC_LINK` / `CSC_KEY_PASSWORD` 接口并加 `-RequireSigning`；该模式同时要求 Git 工作树干净，缺证书或脏工作树立即失败。密钥材料只由 CI secret store 或本机安全存储注入。

构建输出包含 installer、blockmap、CycloneDX SBOM、npm/pip 漏洞报告、Windows 签名状态和 release manifest。manifest 记录 commit、工作树状态、UTC 时间、DB schema、DBC/config schema hash、运行时和每个产物 SHA-256。

## CI 安装验证

`windows-installer` job 构建明确标识的 unsigned internal 包，安装到中文/空格临时路径，占用 8800，裁剪 PATH 后启动已安装应用；验证 sidecar 崩溃恢复和凭据轮换、11 页在 1366×768/1920×1080 的 22 张截图、simulator 缺失时 offline + 控制 409、二次启动、sidecar 缺失诊断、静默卸载和业务数据保留。

本地证据不能替代独立普通用户 VM、企业杀毒/防火墙、签名证书和历史版本升级 fixture 的验收。
