# Phase 05 Evidence Manifest

| Path | Purpose |
| --- | --- |
| `README.md` | Gate decision, exact commands, limitations |
| `environment.json` | OS, Node, npm, Python, Electron and Vite versions |
| `npm-audit.txt` | `npm audit --audit-level=high` result |
| `pip-audit.txt` | Python dependency audit result |
| `bundle-report.json` | JS chunks, gzip sizes, budgets and assertions |
| `tests/root-test.txt` | Root `npm run test` output |
| `tests/python/quality-manifest.json` | Isolated test profile, temporary data path, randomized UDP base and results |
| `tests/python/backend-coverage.json` | Backend coverage data |
| `tests/python/simulator-coverage.json` | Simulator coverage data |
| `tests/python/python_quality.txt` | Full isolated pytest and coverage output |
| `tests/frontend/lint.txt` | ESLint output |
| `tests/frontend/vitest.txt` | Vitest and frontend coverage output |
| `tests/frontend/typecheck.txt` | Vue TypeScript output |
| `tests/frontend/build.txt` | Vite production build output |
| `e2e/e2e-summary.json` | 11-page dual-viewport checks and stale-online 409 evidence |
| `e2e/runtime/runtime_websocket_metrics.json` | WebSocket topic cadence and raw opt-in evidence |
| `e2e/stress-10m/stress_1000fps.json` | 1000fps / 600-second queue, drop, logging and process metrics |
| `e2e/screenshots/` | Current 1920x1080 and 1366x768 Electron captures plus inspection JSON |
| `.github/workflows/quality.yml` | CI quality pipeline definition |
| `ci/29135710440/run.json` | Final successful `quality-gates` Windows run metadata for verified code `24eefac4969015d68c4a959d0d224627262b3a4b` |
| `ci/29135710440/job-logs.txt` | Complete quality and renderer-E2E job logs from the final successful run |
| `ci/29135710440/artifacts/phase-05-quality-29135710440/` | Remote quality output: Python coverage, frontend coverage, lint, typecheck, build, bundle and dependency-audit evidence |
| `ci/29135710440/artifacts/phase-05-e2e-29135710440/` | Remote Electron 43 E2E evidence: version, summary, exact 22 screenshots, runtime cadence and loopback safety checks |

All generated runtime files were created under a phase-five `test` profile using only `127.0.0.1`. Audit evidence under `docs/audit/` and phase-four evidence were not modified or deleted.
