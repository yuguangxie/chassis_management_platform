# 一键检测引擎审计

> **历史基线 / 已被后续审计取代。** 当前结论见 [`current_audit_2026-07-23`](../current_audit_2026-07-23/00_AUDIT_INDEX.md) 和本轮 [P0/P1 验证索引](../verification/software-p0-p1-closure-2026-07-23/README.md)。

## 静态结构

- `DEFAULT_STEPS` 含 12 个名称，但 engine 不读取 `configs/test_plan.yaml` 的 command/assertion/timeout。
- `_run` 每步仅 sleep，检查 `max alarm >=3` 或 `SOC<30`，然后广播 step_update。
- 无实际档位、驱动、转向、灯光、制动动作与反馈断言。
- 会话保存在进程内 dict；重启不可恢复；可同时执行多个会话。
- 未调用 SafetyInterlockService、safe_stop 或数据库 repository。

## 状态机动态测试

| 场景 | 期望 | 实际 |
| --- | --- | --- |
| pause | 步骤停止推进 | 3 步时暂停，450ms 后已 8 步，最终 PASS |
| resume | 从暂停点继续 | 仅修改 status，没有真正等待机制 |
| abort | 终止并保持 ABORTED | 后台继续，最终覆盖为 PASS |
| emergency-stop | 立即停车并终止 | 锁存急停，任务继续并 PASS |
| 两会话并发 | 拒绝或排队 | 两个均同时执行 |
| CAN1/CAN2 断开 | 阻止开始/FAIL | 12 步 PASS |
| session persistence | 落库 | test_sessions 仍 0 行 |

证据：[eol_state_machine.json](evidence/tests/eol_state_machine.json)。

## Profile

- normal_pass：PASS，12 步。
- bms_low_soc：FAIL，但在“上电自检”即失败，不是 BMS step。
- warning_fault：FAIL，但在第 1 步失败，未走告警复查策略。
- steering_no_response：错误 PASS。
- brake_fail：错误 PASS。
- CAN 断开：错误 PASS。
- DBC 未加载、数据库运行期变为不可写：没有专门动态用例；静态代码表明 engine 不检查，结论为未实现而非已通过。
- 用户中止/急停：动态失败。

## 生产判定

当前是 UI 演示所需的异步步骤播放器，不是可用于车辆下线判定的测试引擎。任何 PASS 结论均不能作为生产放行依据。
