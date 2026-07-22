# 安全与生产配置

更新日期：2026-07-22。

## 配置来源和信任级别

`dev/mock/test` 可从仓库回环模板启动，并显式标记 `config_trust=repository-default`。`production` 不接受仓库模板：启动前必须将通过 schema 校验并由本机 `CHASSIS_CONFIG_SIGNING_KEY` 签名的包放到 `CHASSIS_ACTIVE_CONFIG_PATH`（默认 `<data_root>/config/active-package.json`），加载后标记 `config_trust=signed-package`。缺文件、缺 key、签名错误或 profile 不一致均在启动阶段 fail-closed。

## data_root 生命周期

签名配置中的 `data_root` 是所有生产数据路径的唯一真源。数据库、应用日志、Raw CAN、解码信号、报告、导出、临时文件、备份和打印任务均按 `docs/DATA_LIFECYCLE.md` 的固定布局派生。系统设置 API 会拒绝单独修改 `database_path`、`report_directory`、`log_directory` 等派生字段；变更根目录必须制作新签名配置包、dry-run、管理员 APPLY，并按数据迁移方案重启。

环境变量新增：

- `CHASSIS_MIN_FREE_BYTES`：启动和运行期最低剩余空间，默认 100 MiB；
- `CHASSIS_PRINT_BACKEND`：dev/mock/test 为 `virtual`，production 必须为 `windows`；
- `CHASSIS_DATA_DIR`：仅作为未加载 signed package 前的引导默认根。

仓库模板不得包含现场路径、打印机名、账号或秘密。

生产 schema 覆盖：runtime profile、网卡及 bind address、CAN1/CAN2 协议和 endpoint、精确 source allowlist、车型、完整 DBC SHA-256、检测方案版本、data root、工位、打印机。仓库仅提交 `configs/production-config.template.json` 的回环/占位值，不含现场 IP、账号或密钥。

签名流程：

```powershell
$env:CHASSIS_CONFIG_SIGNING_KEY = '<从本机秘密存储注入的随机值，至少32字符>'
python scripts/sign_configuration.py configs/production-config.local.json `
  C:\ProgramData\ChassisEOL\config\active-package.json --issuer plant-admin
```

`production-config.local.json` 必须位于仓库外。签名 key 不传给浏览器，不写入 package，也不提交版本库。

## `configs/safety_interlock.yaml`

`feedback_dependencies` 分为 `base`、`drive`、`steering`、`brake`。每条要求的字段由 Pydantic 明确校验：

| 字段 | 含义 |
|---|---|
| `id` / `label` | 稳定规则 ID 与 UI 标签 |
| `signals` | 可接受的等价信号键，至少一个 |
| `channel` | `CAN1` 或 `CAN2` |
| `max_age_ms` | 50..10000 ms |
| `expected_can_ids` | 允许的来源 CAN ID 集合 |
| `allowed_values` | 可选枚举白名单 |
| `minimum` / `maximum` | 可选有限值合理范围，minimum 不得大于 maximum |

`safe_stop` 支持 `post_confirmation_policy`、`retry_ms`、`hold_period_ms` 与 `hardware_validated`。提交的安全默认值为停止发送、50 ms 重试/保持周期以及硬件未验证。

## `configs/station.yaml`

`dbc` 配置包含：

```yaml
dbc:
  require_for_control_in_production: true
  allow_raw_only_in_nonproduction: true
  approved_vehicle_series: JD
  approved_sha256: 387ae48bd84852c8a6401653f96d1f7fca2a604c90fad018db800bf548ab468c
```

SHA-256 对应当前仓库的 `assets/Yunle_CAN_integrated_candb_jd.dbc`。任何 DBC 内容变化都必须经审批后更新完整 hash，并重新执行本工作包测试；禁止截断 hash。

## 通道配置

`ChannelConfig.validate_source_endpoint` 默认 `true`。批准来源端口为 `simulated_device_port`（Mock/test 存在时），否则为 `device_port`。production 不应关闭来源校验；若设备源端口不固定，应先通过真实只监听验证修改设备配置或重新设计授权策略，不得直接放宽为任意来源。

非 production profile 强制后端监听地址、本地 CAN 地址、设备地址和 source allowlist 都是回环。production 模板仍是回环占位且不能直接启动；现场端点必须通过仓库外签名包批准。

## production 启动门槛

`RuntimeConfig` 在 production 配置加载时即要求：

- 签名 active package 存在且 HMAC-SHA256、schema version、runtime profile 校验通过；
- `require_dbc_for_control=true`；
- 64 位十六进制 `approved_dbc_sha256`；
- 非空批准车型。

运行时联锁还要求实际 DBC loaded/hash/车型一致以及 safe-stop 策略 `hardware_validated=true`。配置应用先 dry-run 展示 diff；正式 APPLY 前检查端口绑定、数据库/data root、控制空闲和 DBC，应用后检查 transport，production 还必须收到批准来源帧，否则自动回滚。普通控制仍受硬件验证门槛阻断，这是预期的 fail-closed 行为。

## 统一环境变量

根 `.env.example` 是唯一名称清单。后端启动脚本读取 `CHASSIS_BACKEND_HOST`、`CHASSIS_BACKEND_PORT`、`CHASSIS_RUNTIME_PROFILE`；默认 host 为 `127.0.0.1`。非 production 将非回环 host 视为配置错误。路径使用 `CHASSIS_DATA_DIR/CONFIG_DIR/ASSETS_DIR/ACTIVE_CONFIG_PATH`；身份使用 `CHASSIS_SESSION_TTL_SECONDS`、`CHASSIS_AUTH_MAX_FAILED_ATTEMPTS`、`CHASSIS_AUTH_LOCKOUT_SECONDS`。秘密变量只允许在本机运行时注入。

安装包默认 `CHASSIS_DESKTOP_RUNTIME_PROFILE=mock`，缺省时仍为 mock。Electron 自行设置动态 `CHASSIS_BACKEND_PORT`、`CHASSIS_LOOPBACK_CAN_PORT_BASE`、资源路径、userData data_root 和每次启动的 `CHASSIS_SIDECAR_TOKEN`；现场不得手工固定 sidecar token。production 选择、active package 和验签 key 必须通过本机批准的外部启动环境注入，禁止进入 Vite 变量或安装资源。
