# 项目基线

> **历史基线 / 已被后续审计取代。** 当前结论见 [`current_audit_2026-07-23`](../current_audit_2026-07-23/00_AUDIT_INDEX.md) 和本轮 [P0/P1 验证索引](../verification/software-p0-p1-closure-2026-07-23/README.md)。

## 环境

| 项目 | 值 | 证据 |
| --- | --- | --- |
| 审计时间 | 2026-07-10 12:30:00 +08:00 | evidence/commands/audit_time.txt |
| 操作系统 | Windows 10 Pro 10.0.19045 x64 | evidence/commands/os_version.txt |
| Python（backend venv） | 3.14.3 | evidence/commands/backend_python_version.txt |
| uv | 0.10.7 | evidence/commands/uv_version.txt |
| conda | 不可用 | evidence/commands/conda_version.txt |
| Node | v22.22.2 | evidence/commands/node_version.txt |
| npm | 10.9.7 | evidence/commands/npm_version.txt |
| Electron | 31.7.7 | evidence/commands/electron_version.txt |
| 前端 | Vue 3.5.39 / Pinia 2.3.1 / Router 4.6.4 / ECharts 5.6.0 / Vite 5.4.21 / TS 5.9.3 | evidence/commands/npm_list.txt |
| 后端 | FastAPI + asyncio + Pydantic + SQLite + cantools | backend/pyproject.toml；evidence/commands/pip_freeze.txt |

## 目录与组件

- `desktop/`：Vue 3 renderer、Pinia、Hash Router、ECharts、Electron `main.cjs/preload.cjs`。
- `backend/app/`：FastAPI、UDP gateway、DBC、控制、EOL、报告、存储和 WebSocket。
- `simulator/`：Python profile 驱动 CAN frame simulator。
- `configs/`：station/channels/thresholds/DBC override/test plan/report/storage/theme。
- `assets/Yunle_CAN_integrated_candb_jd.dbc`：实际加载 39 messages、170 signals，SHA 前缀 `387ae48bd84852c8`。
- 完整文件树：[project_file_inventory.txt](evidence/commands/project_file_inventory.txt)。

## Git

当前目录及父级不是 Git 工作树，无法取得 commit hash；`git status` 和 `git log -1` 的失败输出已保存：[git_status.txt](evidence/commands/git_status.txt)、[git_log_last.txt](evidence/commands/git_log_last.txt)。因此审计无法绑定不可变提交，这是可复现性限制。

## 可用命令

- 后端：`backend/.venv/Scripts/python.exe scripts/dev_backend.py`
- 仿真：`backend/.venv/Scripts/python.exe scripts/dev_simulator.py --profile normal_pass`
- Web：`cd desktop && npm.cmd run dev:web`
- Electron：`desktop/node_modules/electron/dist/electron.exe .`（依赖已运行 Vite）
- 后端测试：`cd backend && .venv/Scripts/python.exe -m pytest tests -q`
- 仿真测试：`cd simulator && ../backend/.venv/Scripts/python.exe -m pytest tests -q`
- 前端：`npm.cmd run typecheck`、`npm.cmd run build`

## 静态标记数量

| 关键词 | 数量 | 证据 |
| --- | --- | --- |
| TODO | 0 | evidence/commands/search_todo.txt |
| FIXME | 0 | evidence/commands/search_fixme.txt |
| stub | 98 | evidence/commands/search_stub.txt |
| mock | 201 | evidence/commands/search_mock.txt |
| fallback | 155 | evidence/commands/search_fallback.txt |
| NotImplemented | 0 | evidence/commands/search_notimplemented.txt |
| setInterval | 11 | evidence/commands/search_setinterval.txt |
| WebSocket | 44 | evidence/commands/search_websocket.txt |
| any | 112 | evidence/commands/search_any.txt |
| ts-ignore | 0 | evidence/commands/search_ts_ignore.txt |
| eslint-disable | 0 | evidence/commands/search_eslint_disable.txt |
| console.log | 0 | evidence/commands/search_console.log.txt |
| localhost | 0 | evidence/commands/search_localhost.txt |
| 127_0_0_1 | 19 | evidence/commands/search_127_0_0_1.txt |
| 192_168_1 | 26 | evidence/commands/search_192_168_1.txt |

搜索排除了 `node_modules`、`dist` 和审计输出。完整计数见 [static_search_counts.txt](evidence/commands/static_search_counts.txt)。`mock/stub/fallback` 数量包含类型、文案和实现引用，不直接等于功能项数量。
