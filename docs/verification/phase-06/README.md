# Phase 06 — Windows installer evidence

执行日期：2026-07-22（Asia/Shanghai）。源码 HEAD：`3c6c838d1a2275d0b0d463ad3f04ac62293dfa0e`；本地产物从包含本工作包未提交变更的工作树构建，因此明确标记 `unsigned-internal`，不能作为正式生产发行版。

## 结论

- P0-03：打包配置、离线 Python sidecar、资源路径、动态端口、短期进程凭据、诊断/重启/优雅退出、单实例、SBOM/hash/manifest 和签名接口已完成软件收口。
- P0-04：自动安装验证脚本与 Windows CI gate 已实现；本机已完成真实 NSIS 安装/启动/卸载回环验证。独立普通用户干净 VM、企业杀毒/防火墙、批准历史升级包和正式证书仍是外部验收项，因此生产 Gate 仍为 `NOT_READY`。
- 全程未启动 simulator、未访问真实 CAN 设备、未发送真实 CAN。安装态 CAN1/CAN2 均为 offline，控制 API 返回 409。

## 本地结果

- Installer：`Chassis-EOL-Setup-1.0.2-unsigned-internal-x64.exe`
- 安装态 11 页 × 2 视口：22/22；无页面级滚动、无 Failed to fetch。
- 运行时 PATH 不包含 Node/Python/uv；8800 被占用时仍使用动态 localhost 端口。
- sidecar 注入崩溃后有界恢复且凭据轮换；sidecar 文件缺失时生成诊断证据。
- simulator 缺失：全部通道 offline，合法 0x121 请求被安全联锁拒绝为 409。
- 二次启动成功；卸载后业务数据 marker 保留。
- npm audit：0 known vulnerabilities；pip-audit：No known vulnerabilities found。
- Authenticode：`NotSigned`，与 unsigned-internal 标签一致。

详见 `clean-machine/clean-machine-matrix.json`、`clean-machine/installed-e2e/installed-e2e-summary.json`、`release/release-manifest.json`、`release/sbom.cdx.json` 和漏洞/签名报告。
