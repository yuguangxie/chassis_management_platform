# 低速无人车线控底盘生产下线管理平台

可运行工程目录：`chassis_management_platform/`。本项目提供 FastAPI 后端、Electron + Vue 3 桌面端、USR-CAN115 UDP CAN 网关、DBC 自动加载、0x121 安全控制、EOL 一键检测、报告生成和无硬件仿真器。

## 环境

- Python 3.11+
- Node.js 18+
- Windows PowerShell、Linux/macOS shell 均可

## Python 环境

### uv

```bash
cd chassis_management_platform
uv venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
uv pip install -e backend
```

### conda

```bash
cd chassis_management_platform
conda create -n chassis-eol python=3.11 -y
conda activate chassis-eol
pip install -e backend
```

## 启动后端

```bash
python scripts/prepare_dev_config.py
python scripts/dev_backend.py
```

默认 HTTP：`http://127.0.0.1:8800`，WebSocket：`ws://127.0.0.1:8800/ws`。

首次启动不会提供默认账号或固定 token。若本地数据库尚无账号，请从运行数据目录的 `auth/bootstrap-admin.secret` 读取一次性凭据，在桌面登录页建立首个管理员；成功后该文件自动删除。随后由管理员建立 operator/engineer/viewer 账号。完整的干净机和 production 签名配置流程见 `docs/IDENTITY_AND_ACCESS.md`。

所有持久化文件从签名配置的唯一 `data_root` 派生。production 部署、schema migration、备份恢复、retention 和打印依赖分别见 `docs/DEPLOYMENT.md`、`docs/DATABASE_AND_MIGRATIONS.md`、`docs/DATA_LIFECYCLE.md` 和 `docs/REPORTING_AND_PRINTING.md`。

## 启动仿真器

```bash
python scripts/dev_simulator.py --profile normal_pass
python scripts/dev_simulator.py --profile bms_low_soc
python scripts/dev_simulator.py --profile warning_fault
python scripts/dev_simulator.py --profile steering_no_response
python scripts/dev_simulator.py --profile brake_fail
```

仿真器向后端本地端口 CAN1 `127.0.0.1:8234`、CAN2 `127.0.0.1:8235` 发送 USR-CAN115 13 字节帧，并监听后端发往模拟设备的 CAN1 `127.0.0.1:12341`、CAN2 `127.0.0.1:12342`。

## 启动 Electron 桌面端

```bash
cd desktop
npm install
npm run dev
```

也可在根目录使用：

```bash
npm run backend:dev
npm run sim:normal
npm run desktop:dev
npm run test
```

## 测试

```bash
pytest backend/tests -q
pytest simulator/tests -q
python scripts/check_report_dependencies.py
cd desktop
npm run typecheck
npm run build
```

## 关键路径

- 后端入口：`backend/app/main.py`
- CAN 协议：`backend/app/can_gateway/usr_can115.py`
- 0x121 编码：`backend/app/control/control_121.py`
- 安全联锁：`backend/app/control/safety_interlock.py`
- 一键检测：`backend/app/eol/engine.py`
- 仿真器：`simulator/can_frame_simulator.py`
- 桌面 UI：`desktop/src/`
- Windows 离线打包：`docs/DESKTOP_PACKAGING.md`
- 安装/升级/排障：`docs/WINDOWS_INSTALLATION_UPGRADE_TROUBLESHOOTING.md`

## 真实硬件确认项

- 0x121 周期最终采用 20 ms 还是 10 ms。
- USR-CAN115 设备现场 UDP/TCP 参数、心跳和防火墙设置。
- 实车 BMS 串数、硬件急停独立信号和 PDF 转换工具链。
