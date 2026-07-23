# 测试质量审计

> **历史基线 / 已被后续审计取代。** 当前结论见 [`current_audit_2026-07-23`](../current_audit_2026-07-23/00_AUDIT_INDEX.md) 和本轮 [P0/P1 验证索引](../verification/software-p0-p1-closure-2026-07-23/README.md)。

## 实际执行

| 命令 | 结果 | 证据 |
| --- | --- | --- |
| backend pytest | 30 passed，5 warnings | `evidence/tests/backend_pytest.txt` |
| simulator pytest（项目根） | collection error | `evidence/tests/simulator_pytest.txt` |
| simulator pytest（simulator cwd） | 1 passed | `evidence/tests/simulator_pytest_from_simulator_dir.txt` |
| backend coverage | 无 pytest-cov，无法执行 | `evidence/tests/backend_coverage_attempt.txt` |
| npm install | 成功，4 vulnerabilities | `evidence/tests/npm_install.txt` |
| npm typecheck | 通过 | `evidence/tests/frontend_typecheck.txt` |
| npm build | 通过，bundle warning | `evidence/tests/frontend_build.txt` |
| npm test | script 不存在 | `evidence/tests/frontend_test_attempt.txt` |
| npm lint | script 不存在 | `evidence/tests/frontend_lint_attempt.txt` |
| root npm test | pytest 不在 PATH | `evidence/tests/root_npm_test.txt` |

成功测试用例共 31 条，31 条通过；但推荐的根目录仿真测试发生 1 个 collection error。不能把“成功套件 100%”解释为质量充分。

## 覆盖情况

- 已有：13-byte 基本编解码、粘/半包、DLC/保留位、0x121 补码/边界、安全联锁超速/急停、DBC load、部分 dashboard/API、系统维护 gate。
- 缺失：UDP datagram 边界、背压、WebSocket 节流/重连、真实 EOL 12 步、暂停/中止/急停并发、报告渲染、数据库事务、Electron UI、端到端按钮、长时运行。
- 现有 EOL、安全和报告缺陷没有被原测试捕获，说明测试更偏结构/HTTP 存在性。

测试评分 **55/100**。新增的 `scripts/audit_*` 是审计探针，不是可替代产品测试的正式套件。
