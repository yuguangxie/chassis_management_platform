# AGENTS.md - Codex 工程指导

> 项目：低速无人车线控底盘生产下线管理平台。本文档属于 Codex 实施资料包，面向产品、架构、CAN 协议、测试系统、前端 UI 和部署实现。

## 项目背景
你正在实现《低速无人车线控底盘生产下线管理平台》。这是产线下线检测软件，涉及真实车辆运动控制。任何可能发送 CAN 控制帧的修改都必须优先考虑安全、审计和可测试性。

## 技术栈
- Frontend：Vue 3 + TypeScript + Vite + Pinia + Vue Router + ECharts。
- Desktop：Electron 首版优先。
- Backend：Python 3.11+ + FastAPI + asyncio + pydantic。
- CAN：UDP/TCP socket，USR-CAN115 13 字节协议。
- DBC：cantools 或项目内等价解析服务。
- DB：SQLite。
- Report：python-docx，PDF 转换按部署环境配置。

## 目录结构约定
- `frontend/`：Vue/Electron UI。
- `backend/`：FastAPI、CAN、DBC、控制、检测、报告。
- `configs/`：初始配置，不存放密钥。
- `docs/`：架构、接口、UI、检测、部署文档。
- `tests/`：单元、集成、Mock、台架辅助测试。
- `tools/`：导入、迁移、日志转换脚本。

## 构建命令建议
```bash
# backend
cd backend
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell 按实际调整
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8800

# frontend
cd frontend
npm install
npm run dev
npm run build
```

## 测试命令建议
```bash
pytest -q
pytest tests/test_usr_can115_protocol.py -q
pytest tests/test_control_121_encoding.py -q
pytest tests/test_safety_interlock.py -q
npm run test
npm run typecheck
npm run lint
```

## 编码规范
- Python 使用类型标注、pydantic 模型、清晰异常类型和结构化日志。
- TypeScript 禁止 `any` 泛滥，API 类型集中维护。
- 配置读取必须有默认值、校验和错误提示。
- 所有时间戳统一存 UTC ISO8601，UI 转本地时间显示。
- 每次修改涉及配置或接口时，同步更新文档和测试。

## 安全红线
- 禁止 UI 直接发送 CAN。
- 禁止绕过 SafetyInterlockService。
- 禁止默认启用 0x123、0x126、0x710、0x715 或 CANopen NMT。
- 禁止在严重告警、急停、关键反馈离线、数据库不可写时执行运动控制。
- 禁止将 Mock 模式伪装为真实硬件模式。

## CAN 通信约束
- 默认 UDP，UI 保留 TCP。
- 每路 CAN 独立 socket、接收缓冲、发送队列、统计和日志。
- USR-CAN115 标准转换模式：13 字节一帧，Byte0 帧信息，Byte1-4 CAN ID 高位在前，Byte5-12 固定 8 字节数据。
- 帧信息：Bit7 FF，Bit6 RTR，Bit5-Bit4 保留必须为 0，Bit3-Bit0 DLC 0-8。
- 数据不足 8 字节补 0，接收时按 DLC 截取有效数据但保存 8 字节原始区。

## DBC 语义修正规则
- 0x100-0x109 为 BMS；0x104-0x109 是 cell 分段兼容，不代表当前一定 24 串。
- 0x101 `Charge_or_Discharge_State`：0 idle，1 charging，2 discharging，3 reserved。
- 0x102 1 bit 保护状态按 unsigned bool；Balance 位图按无符号位图。
- 0x121-0x126 为整车/底盘控制范围，默认只主动发送 0x121。
- 电机 CANopen PDO 中 `Torque_req`/`Torque_feed` 是电机相电流 A，raw × 0.1 A，不是 Nm。

## 0x121 编码规则
- 0x121 是主控制报文，默认周期 20 ms，可配置。
- 前/后转角控制值范围 -120..120，必须按 int8 补码写入 8 bit。
- 示例：-120=0x88，-60=0xC4，0=0x00，60=0x3C，120=0x78。
- 控制值与实际传感器目标值关系：实际目标值 = 控制值 × 1.4；控制值 = 实际目标值 / 1.4。
- 编码函数必须单测覆盖边界、负值、超限裁剪和示例。

## 0x123 / 0x126 默认禁用
- 0x126 转向角速度范围 126..525 deg/s，默认不发送。
- 只有管理员维护模式、台架安全条件、配置显式开启时才允许扩展报文。
- 一键检测不得主动下发 0x123/0x126。

## UI 风格规则
- 深蓝工业科技风，左侧导航，顶部状态栏，大量卡片。
- 主色蓝，正常/PASS 绿色，警告/暂停黄色，故障/FAIL/急停红色。
- 曲线图深色网格，表格高对比，数字仪表采用工业风。
- 所有页面必须有空状态、加载状态和异常状态。

## 日志和报告规则
- 原始 CAN、解码信号、检测步骤、断言、操作动作和报告生成都必须落库或落文件。
- 报告必须包含软件版本、DBC hash、配置版本、检测方案版本和操作员。
- 删除报告需管理员权限并保留审计记录。

## Mock 测试要求
- 任何核心功能都必须能在 MockCanGateway 下测试。
- Mock 支持正常、超时、告警、BMS异常、转角不跟随、速度不跟随、数据库失败等场景。

## Definition of Done
- 代码通过单元测试、类型检查和 lint。
- 新增或修改的 API 有文档和测试。
- 安全逻辑有失败路径测试。
- UI 有 Mock 数据演示。
- 相关文档、配置、Prompt 或 Skill 已更新。
- 任何不确定项记录到 `docs/20_risk_and_open_questions.md`。
