# Phase 05 Verification: Quality Engineering and Reproducible Delivery

## Gate Result

**Phase 05 passed remote Windows CI verification.** The accepted evidence is GitHub Actions run [`29135710440`](https://github.com/yuguangxie/chassis_management_platform/actions/runs/29135710440), workflow `quality-gates`, triggered by `push` on 2026-07-11.

- Verified code commit: `24eefac4969015d68c4a959d0d224627262b3a4b`
- Evidence archive commit: recorded after the archive commit is created; it is intentionally separate from the verified-code commit.
- CI results: `quality` success; `renderer-e2e` success.
- Electron executed by the Windows runner: `v43.1.0`.

## Remote Windows Evidence

| Gate | Result | Archived evidence |
| --- | --- | --- |
| Isolated backend and simulator suites | PASS | `ci/29135710440/artifacts/phase-05-quality-29135710440/python/quality-manifest.json` |
| Backend coverage | PASS: 74.66% statements | `ci/29135710440/artifacts/phase-05-quality-29135710440/python/backend-coverage.json` |
| Simulator coverage | PASS: 43.33% statements | `ci/29135710440/artifacts/phase-05-quality-29135710440/python/simulator-coverage.json` |
| Frontend lint, typecheck, Vitest and build | PASS: 6 files, 9 tests | `ci/29135710440/artifacts/phase-05-quality-29135710440/{lint,typecheck,vitest,build}.txt` |
| Frontend coverage baseline | PASS: 45.31% statements, 47.68% lines | `ci/29135710440/artifacts/phase-05-quality-29135710440/frontend-coverage/coverage-final.json` |
| Dependency audits | PASS: npm high/critical 0; pip-audit no known vulnerabilities | `ci/29135710440/artifacts/phase-05-quality-29135710440/{npm-audit,pip-audit}.txt` |
| Bundle budget | PASS: ECharts 367,892 gzip bytes; total JS 497,643 gzip bytes | `ci/29135710440/artifacts/phase-05-quality-29135710440/bundle.txt` |
| Electron E2E | PASS: 11 pages x 2 viewports = 22 screenshots | `ci/29135710440/artifacts/phase-05-e2e-29135710440/` |
| Page-level scroll | PASS: 0 failures | `ci/29135710440/artifacts/phase-05-e2e-29135710440/e2e-summary.json` |
| Failed-to-fetch banners | PASS: 0 | `ci/29135710440/artifacts/phase-05-e2e-29135710440/e2e-summary.json` |
| White native controls | PASS: 0 | `ci/29135710440/artifacts/phase-05-e2e-29135710440/e2e-summary.json` |
| Renderer errors | PASS: 0 console and page errors | `ci/29135710440/artifacts/phase-05-e2e-29135710440/e2e-summary.json` |
| Simulator offline safety gate | PASS: offline after 2319 ms; engineer control request returned HTTP 409 | `ci/29135710440/artifacts/phase-05-e2e-29135710440/e2e-summary.json` |
| Loopback boundary | PASS: non-loopback requests 0 | `ci/29135710440/artifacts/phase-05-e2e-29135710440/e2e-summary.json` |
| WebSocket cadence and raw opt-in | PASS | `ci/29135710440/artifacts/phase-05-e2e-29135710440/runtime/runtime_websocket_metrics.json` |

The final run metadata and full job log are [run.json](ci/29135710440/run.json) and [job-logs.txt](ci/29135710440/job-logs.txt). The E2E artifact contains exactly 22 PNG files under `phase-05-e2e-29135710440/screenshots/`; two additional PNG files in the quality artifact are Istanbul coverage-report assets and are not screenshots.

## Reproducible Commands

From the repository root:

```powershell
npm.cmd --prefix desktop run lint
npm.cmd --prefix desktop run test
npm.cmd --prefix desktop run typecheck
npm.cmd --prefix desktop run build
npm.cmd --prefix desktop run test:e2e
npm.cmd --prefix desktop run test:integration
npm.cmd --prefix desktop run test:e2e:verify
```

The long 1000fps/600-second workload remains an explicit `workflow_dispatch` option (`long_runtime`) and is documented in the prior local evidence. It was not claimed as part of this push-triggered CI run.

## Safety Boundary

阶段五门禁已经通过远程 Windows CI 验证。

阶段六可以开始。阶段六仍然只能在封闭的 `127.0.0.1` / Python simulator 环境中执行。真实车辆、真实台架或外部设备接入仍然需要安全负责人书面批准。

The CI workflow rejects `CHASSIS_E2E_ELECTRON`, runs only the installed Electron 43.1.0 binary, and uses test-profile loopback UDP/HTTP/WebSocket endpoints. It does not authorize a real vehicle connection.

## Non-blocking Follow-up

Frontend coverage is an enforced baseline rather than broad page coverage: `BarChart.vue`, `DonutChart.vue`, and several dashboard paths need additional focused tests. The ECharts split is within the explicit budget, but further per-chart imports remain a performance optimization.
