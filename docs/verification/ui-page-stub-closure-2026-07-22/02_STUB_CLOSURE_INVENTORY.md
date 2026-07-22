# Stub、固定值与无 handler 控件收口清单

## 审计方法

扫描 11 个页面中的 `button/@click/disabled`、Toast、固定数组、fallback、静态 select，以及 backend API 中直接返回 `ok: true` 的入口；再逐项确认是否存在真实校验、持久化和审计副作用。Toast 仅作为结果展示，不再被视为功能完成证据。

## 已接通真实链路

| 页面 | 原问题 | 当前处理 |
|---|---|---|
| Network | 静态 FPS/错误数组、固定 ping、参数只读、应用失败无可见回滚 | 使用 `/can/statistics/monitor` 和 `/can/channels/self-test`；ping 未测量为 `null`；管理员可编辑；保留已应用快照，失败恢复；后端原子恢复 manager/config |
| Manual Control | 反馈仅有几个摘要值，看不到联锁依赖质量 | `/control/manual-feedback` 返回逐 rule 的 present、age、quality、source、range/checks、threshold、blocking；离线值和曲线屏蔽 |
| Report | 打印只是提交动作 | 显示 printer availability/default、job id、spooler id、attempts、queued/printing/completed/failed/cancelled、取消和重试 |
| System Settings | import/export、cleanup、path、backup/restore 只停留在页面按钮 | 签名配置文件 dry-run/diff/apply；data_root 派生只读路径；一致性备份/校验恢复；cleanup dry-run/确认；storage health 复检 |
| CAN Monitor | “更多”没有 handler，复制图标没有 handler | “更多/收起”切换真实文件列表；帧数据复制调用 clipboard 并显示失败状态 |
| History | 固定 `op01/op02`、固定工位、固定 2026 日期；查询失败仍提示成功 | 操作员/工位从返回会话动态生成；日期默认空；失败提示“查询失败”；离线趋势清空 |
| 所有页面 | 状态表达不一致 | 统一 `PageDataState`，权限错误优先于 stale/empty，错误优先于 fallback |

## 明确禁用并标注“尚未实现”

| 页面 | 控件 | 处理与理由 |
|---|---|---|
| 总览 | 自定义布局 | 禁用；当前没有布局 schema/editor，不能只 Toast |
| Network | 联机帮助 | 禁用；尚无内置帮助资源 |
| Network | 网卡选择 | 禁用；生产网卡只能通过签名配置生命周期变更，避免绕过校验 |
| Network | 图表时间范围 | 禁用；后端当前只提供既定窗口/累计统计 |
| CAN Monitor | 原始数据/DBC 信息/发送历史详情页签 | 禁用并标注；现有数据已在同页或系统设置展示，独立视图尚无 API 契约 |
| CAN Monitor | 帧详情全屏/关闭图标 | 禁用并标注；不再伪装可点击 |
| Manual Control | 自定义布局 | 禁用；控制页布局变更需独立安全设计 |
| Auto Test | 自定义布局 | 禁用；检测步骤固定为审批方案 |
| Alarm | 历史上一页/下一页 | 禁用；后端当前告警 dashboard 未提供分页契约 |
| Realtime Curve | 信号列表列设置 | 禁用；无列配置 schema |
| Report | 列设置、密度、预览菜单 | 禁用；无持久化模型 |
| Report | 关联原始 CAN/信号/断言/日志分标签和查看图标 | 非当前统一会话摘要标签禁用；待建立独立分页 API 后实现 |
| Report | 统计时间范围 select | 禁用；当前 API 窗口固定，不能让 UI 假装可选 |
| System Settings | 直接选择生产 DBC | 禁用；生产 DBC 必须随签名配置包部署 |
| System Settings | 覆盖规则/版本详情按钮 | 禁用并说明内容已在当前卡片展示 |

## 固定数组保留项

以下数组是显示枚举或安全边界，不属于 Stub：角色层级、状态颜色、CAN1/CAN2 通道枚举、0x121 挡位/模式枚举、告警等级图例、批准的反馈 rule 标签。页面筛选中的操作员、工位、报告类型已经改为从后端数据派生。

## backend `ok: true` 复核

下列接口虽然响应包含 `ok: true`，但不是固定成功 Stub：

- 信号 watchlist/layout：写入 `PreferenceService` 并记录操作审计；未知信号返回 422。
- CAN clear-display：清理 runtime buffer 并记录审计；导出会生成 data_root 下真实文件。
- 告警确认/定位：验证 alarm/CAN frame，更新 runtime/SQLite 并记录审计；不存在返回 404/422。
- 历史 open-detail/export：先验证 session 或生成真实导出文件，并记录审计。
- 配置 import/apply：执行签名、schema、版本、diff、权限、健康检查和失败回滚，dry-run 不改变运行态。
- 打印：创建真实或虚拟后端 job，状态机可查询、取消、失败和重试。

## 残余范围

本工作包不新增真实车辆控制能力，不打开 0x123/0x126/NMT，不扩大 CAN2 `0x121` 白名单。上述禁用项只能在建立后端契约、权限、审计和失败测试后解除。
