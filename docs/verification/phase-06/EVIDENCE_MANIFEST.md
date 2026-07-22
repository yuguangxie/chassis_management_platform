# Evidence manifest

| 证据 | 内容 |
|---|---|
| `clean-machine/installed-e2e/*.png` | 已安装应用 11 页在 1366×768、1920×1080 的 22 张截图 |
| `clean-machine/installed-e2e/installed-e2e-summary.json` | route、尺寸、滚动、fetch、offline、409、sidecar 恢复断言 |
| `clean-machine/sidecar-startup-failure/startup-failure.json` | sidecar 缺失/被拦截的诊断路径 |
| `clean-machine/clean-machine-matrix.json` | 安装、二次启动、端口占用、卸载数据保留及未执行外部项 |
| `release/release-manifest.json` | 版本、commit/dirty、签名级别、schema、DBC/config hash 和产物 hash |
| `release/sbom.cdx.json` | CycloneDX 1.5 Node/Python 依赖清单 |
| `release/npm-audit.json` / `pip-audit.json` | 构建时漏洞扫描结果 |
| `release/signing-status.json` | Windows Authenticode 结果与正式发布资格 |

所有动态验证只使用 127.0.0.1 和临时 data_root。未使用、连接或探测真实 CAN 设备。
