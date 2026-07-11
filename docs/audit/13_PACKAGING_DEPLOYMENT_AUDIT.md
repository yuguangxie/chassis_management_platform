# 打包与部署审计

## 已验证

- Windows 开发：backend、Vite、Electron 可分别启动。
- `npm run build` 和 `npm run electron:build` 均完成 Vite bundle。
- DBC 与 configs 以源码相对路径可被开发环境找到。
- frame:false、菜单隐藏生效。

## 生产阻断

`electron:build` 实际脚本仅 `vite build`，没有 electron-builder/forge、安装器、签名或资源清单。`main.cjs` 无论环境都 `loadURL(http://127.0.0.1:5173)`，不 `loadFile(dist/index.html)`；也不拉起/监控 FastAPI，不包含 Python runtime。Vite 停止后所谓生产 app 无法显示。

## 部署矩阵

| 项目 | 状态 |
| --- | --- |
| Windows 开发启动 | 已验证 |
| Linux 开发启动 | 未验证（当前仅 Windows） |
| uv 环境 | 可用，但根目录无统一 venv |
| conda | 当前机器不可用 |
| Electron 开发 | 已验证依赖 Vite |
| Electron installer | 缺失 |
| 后端打包/Python runtime | 缺失 |
| 自动拉起/退出后端 | 缺失 |
| 首次数据目录初始化 | 开发路径可建，生产路径未验证 |
| 生产/dev 配置分离 | 不完整，默认生产 IP 与 simulator 不匹配 |
| LibreOffice/PDF 环境 | 未配置；ReportLab 输出中文失败 |
| 端口冲突/防火墙 | 仅看到 bind fallback；未做生产防火墙验证 |
| 自动启动/崩溃恢复 | 缺失 |
| 升级/回滚 | 缺失 |
| 离线部署 | 缺失 |

依赖审计有 2 high + 2 moderate。部署评分 **20/100**，当前只支持开发运行。
