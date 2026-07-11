# 11 页功能实现审计

## 计分口径

- 加权功能完成率：`(REAL + 0.5×PARTIAL + 0.25×MOCK + 0.1×STUB) / 总项数`。
- 真实实现率：`REAL / 总项数`。
- Mock/Stub 不计为真实实现；接口存在但未形成业务闭环为 PARTIAL。

| 页面 | 总项 | REAL | PARTIAL | MOCK | STUB | 缺失 | 功能% | 真实% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| /overview | 10 | 0 | 5 | 5 | 0 | 0 | 37.5 | 0.0 |
| /network-config | 13 | 2 | 5 | 5 | 1 | 0 | 45.0 | 15.4 |
| /can-monitor | 13 | 6 | 1 | 4 | 2 | 0 | 59.2 | 46.2 |
| /signal-dashboard | 14 | 0 | 10 | 2 | 2 | 0 | 40.7 | 0.0 |
| /realtime-curve | 13 | 0 | 7 | 4 | 2 | 0 | 36.2 | 0.0 |
| /manual-control | 17 | 10 | 5 | 2 | 0 | 0 | 76.5 | 58.8 |
| /auto-test | 14 | 0 | 10 | 3 | 0 | 1 | 41.1 | 0.0 |
| /alarm-diagnosis | 11 | 0 | 7 | 2 | 2 | 0 | 38.2 | 0.0 |
| /report-management | 16 | 0 | 7 | 3 | 5 | 1 | 29.7 | 0.0 |
| /history | 12 | 2 | 3 | 5 | 2 | 0 | 41.2 | 16.7 |
| /system-settings | 15 | 3 | 9 | 1 | 2 | 0 | 53.0 | 20.0 |

总计 148 项：REAL 23、PARTIAL 69、MOCK 36、STUB 18、MISSING 2。总体加权功能完成率 **46.1%**，真实实现率 **15.5%**。


## 总览 `/overview`

| 功能 | 状态 | 依据 |
| --- | --- | --- |
| KPI 数据来源 | PARTIAL | API 混合 SQLite 结果和 fallback；数据库无会话记录 |
| CAN1/CAN2 状态 | PARTIAL | 读取真实 gateway，但 fps 算法和顶部状态存在不一致 |
| 当前车辆 | MOCK | 固定 YL-JD-001 |
| 告警摘要 | PARTIAL | 最高等级可来自 SignalStore，其余保护项固定 |
| 快捷入口 | PARTIAL | 路由可用，打开目录为 Stub，安全停车仅部分实现 |
| 今日结果图 | MOCK | 固定 18/17/1 |
| 小时产能图 | MOCK | 固定序列 |
| 帧率趋势 | MOCK | 固定趋势 |
| 最近会话 | MOCK | 数据库为空后回填固定会话 |
| 安全停车快捷按钮 | PARTIAL | 调用后端，但只发一次停车帧 |

合计：REAL 0、PARTIAL 5、MOCK 5、STUB 0、MISSING 0、UNVERIFIED 0；加权功能完成率 **37.5%**，真实实现率 **0.0%**。


## 网络配置 `/network-config`

| 功能 | 状态 | 依据 |
| --- | --- | --- |
| 读取配置 | PARTIAL | 返回运行配置与固定 NIC 信息 |
| 保存配置 | PARTIAL | 校验并更新配置结构，运行 gateway 不支持完整热切换/持久化闭环 |
| UDP/TCP 切换 | PARTIAL | UI/API 接受 TCP，实际仅有 UdpCanGateway |
| CAN1 启停 | REAL | 实际绑定/关闭 socket |
| CAN2 启停 | REAL | 实际绑定/关闭 socket |
| 自检 | STUB | self-test 明确 stub=true |
| Ping | MOCK | 固定 0.92ms |
| UDP 回环 | MOCK | 固定 pass |
| 13 字节合法率 | MOCK | 固定 99.96% |
| DLC/保留位校验 | MOCK | 协议 codec 有校验，但诊断接口不执行测试 |
| 粘包/半包统计 | MOCK | 固定 0/0 |
| 恢复默认 | PARTIAL | 接口可恢复默认对象，未证明 gateway 原子重连 |
| 端口检测 | PARTIAL | 状态主要来自固定配置 |

合计：REAL 2、PARTIAL 5、MOCK 5、STUB 1、MISSING 0、UNVERIFIED 0；加权功能完成率 **45.0%**，真实实现率 **15.4%**。


## CAN 监控 `/can-monitor`

| 功能 | 状态 | 依据 |
| --- | --- | --- |
| 按 CAN ID 聚合 | REAL | 后端 latest map + 前端 Record |
| 新帧 upsert | REAL | 同 ID 更新对应行 |
| CAN ID 排序 | REAL | 三态排序 |
| 行选择 | REAL | 选中 ID 联动请求详情 |
| 详情解码 | PARTIAL | 框架联动真实，signals 内容对常用 ID 硬编码 |
| 0x77 详情 | MOCK | 固定 Normal 信号 |
| 0x121 详情 | MOCK | 固定示例数据 |
| 暂停刷新 | REAL | pending map 暂存后 flush |
| 过滤 | REAL | 通道/ID/报文名/方向/状态 |
| 导出 CSV | STUB | 后端 stub |
| 原始日志导出 | STUB | 后端 stub |
| 历史文件 | MOCK | 固定文件清单 |
| 统计图 | MOCK | 固定分布、趋势、抖动和错误数 |

合计：REAL 6、PARTIAL 1、MOCK 4、STUB 2、MISSING 0、UNVERIFIED 0；加权功能完成率 **59.2%**，真实实现率 **46.2%**。


## 信号仪表盘 `/signal-dashboard`

| 功能 | 状态 | 依据 |
| --- | --- | --- |
| BMS | PARTIAL | SignalStore 覆盖部分字段，其余 fallback |
| 车辆状态 | PARTIAL | 部分真实信号 + fallback |
| 四轮轮速 | PARTIAL | 可读解码值，单位/映射仍有限 |
| 转向反馈 | PARTIAL | 实时反馈可覆盖 |
| 电机转速 | PARTIAL | 缺失时回填 |
| 电机相电流 | PARTIAL | 文案单位 A 正确，数据源不完整 |
| 心跳 | PARTIAL | 收到 0x703/0x704 可更新 |
| 灯光 | PARTIAL | 部分信号/回填 |
| 制动 | PARTIAL | 部分信号/回填 |
| 告警 | PARTIAL | SignalStore 最高等级 |
| Watchlist | MOCK | 固定 8 行，少量值覆盖 |
| 趋势图 | MOCK | 固定 sparkline |
| 自定义布局 | STUB | 按钮有反馈，无布局引擎 |
| 保存关注信号 | STUB | 后端接口明确 stub |

合计：REAL 0、PARTIAL 10、MOCK 2、STUB 2、MISSING 0、UNVERIFIED 0；加权功能完成率 **40.7%**，真实实现率 **0.0%**。


## 实时曲线 `/realtime-curve`

| 功能 | 状态 | 依据 |
| --- | --- | --- |
| 信号分组 | MOCK | 固定 group/config |
| 信号勾选 | PARTIAL | checkbox 状态未约束实际 series |
| 6 个图表 | MOCK | ECharts 真实渲染，数据固定 |
| 时间窗口 | PARTIAL | 可改查询参数，后端忽略部分语义 |
| 采样率 | PARTIAL | 控件与 query 存在，未执行真实重采样 |
| 降采样 | MOCK | 选项存在，无算法 |
| 暂停/继续 | PARTIAL | 轮询可暂停，WebSocket handler 仍触发加载 |
| 缩放复位 | PARTIAL | 本地图表操作 |
| CSV | STUB | 后端 stub |
| 快照 | STUB | 后端 stub |
| 历史会话 | MOCK | 固定回放元数据 |
| 播放控制 | PARTIAL | 本地游标，seek 未形成后端闭环 |
| 故障跳转 | PARTIAL | 固定故障事件与本地跳转 |

合计：REAL 0、PARTIAL 7、MOCK 4、STUB 2、MISSING 0、UNVERIFIED 0；加权功能完成率 **36.2%**，真实实现率 **0.0%**。


## 手动控制 `/manual-control`

| 功能 | 状态 | 依据 |
| --- | --- | --- |
| 安全联锁 | PARTIAL | 实际发送会 evaluate；展示接口却硬编码 allow |
| 档位 | REAL | 进入真实 0x121 payload |
| 驱动模式 | REAL | 进入真实 payload |
| 目标速度 | REAL | 0.1km/h 编码并受限速阻断 |
| 前后转角 | REAL | 真实 int8 编码 |
| 制动 | REAL | 进入 payload |
| 灯光 | REAL | 进入 payload |
| 0x121 预览 | PARTIAL | API 返回真实 data，但 UI bytes_hex 采用另一套字节排列/比例 |
| int8 补码 | REAL | -120/-60/0/60/120 实测正确 |
| 一次发送 | REAL | 回环仿真器收到 |
| 周期发送 | REAL | 回环仿真器收到 |
| 停止发送 | REAL | scheduler task 停止 |
| 安全停车 | PARTIAL | 只发送一次 N/0/制动帧 |
| 急停 | PARTIAL | 停止周期并锁存，但不下发停车帧 |
| 解除急停 | PARTIAL | 仅清布尔锁存，无静止/反馈复核 |
| 实时反馈 | MOCK | 固定 API |
| 曲线 | MOCK | 固定 API |

合计：REAL 10、PARTIAL 5、MOCK 2、STUB 0、MISSING 0、UNVERIFIED 0；加权功能完成率 **76.5%**，真实实现率 **58.8%**。


## 一键检测 `/auto-test`

| 功能 | 状态 | 依据 |
| --- | --- | --- |
| 会话创建 | PARTIAL | 创建内存会话，不落库 |
| 12 步流程 | PARTIAL | 存在 12 名称但不执行对应动作 |
| 开始 | PARTIAL | 启动简化异步循环 |
| 暂停 | PARTIAL | 状态改 PAUSED，任务继续 |
| 继续 | PARTIAL | 状态接口存在，无真正阻塞点 |
| 中止 | PARTIAL | ABORTED 被最终 PASS 覆盖 |
| 急停 | PARTIAL | 设置锁存但测试任务继续并 PASS |
| 当前测量值 | MOCK | dashboard 固定 |
| 检测断言 | PARTIAL | 引擎仅检查严重告警/SOC，页面断言固定 |
| 步骤日志 | MOCK | dashboard 固定 |
| 曲线 | MOCK | 固定序列 |
| PASS/FAIL | PARTIAL | 转向/制动故障错误 PASS |
| 报告生成 | PARTIAL | 生成文件但内容损坏/不完整 |
| 数据持久化 | MISSING | 核心业务表 0 行 |

合计：REAL 0、PARTIAL 10、MOCK 3、STUB 0、MISSING 1、UNVERIFIED 0；加权功能完成率 **41.1%**，真实实现率 **0.0%**。


## 告警诊断 `/alarm-diagnosis`

| 功能 | 状态 | 依据 |
| --- | --- | --- |
| 0x77 矩阵 | PARTIAL | 部分 SignalStore 值覆盖固定矩阵 |
| 0x102 unsigned bool | PARTIAL | bitmap unsigned 正确，单项保护值不完整 |
| Bitmap | PARTIAL | 真实 16bit 数值可显示 |
| 当前告警 | PARTIAL | 内存告警服务 |
| 历史告警 | MOCK | 固定 5 条 |
| 诊断建议 | MOCK | 固定建议 |
| 人工放行 | STUB | 固定 stub |
| 确认告警 | PARTIAL | 可对内存项 ack |
| 跳转 CAN 帧 | PARTIAL | API stub 后前端路由跳转 |
| 导出诊断 | STUB | 固定 stub |
| 安全停车 | PARTIAL | 调用不完整 safe-stop |

合计：REAL 0、PARTIAL 7、MOCK 2、STUB 2、MISSING 0、UNVERIFIED 0；加权功能完成率 **38.2%**，真实实现率 **0.0%**。


## 报告管理 `/report-management`

| 功能 | 状态 | 依据 |
| --- | --- | --- |
| 扫描目录 | PARTIAL | 确实扫描 data/reports，但响应仍标 stub |
| 报告列表 | PARTIAL | 扫描结果与 Mock 混合 |
| 筛选 | PARTIAL | 对当前混合列表服务端过滤 |
| Word 文件 | PARTIAL | 实际生成 DOCX，但内容乱码 |
| PDF 文件 | PARTIAL | 实际生成 PDF，但中文方块且内容不足 |
| JSON 文件 | PARTIAL | 可打开但缺版本/hash |
| CSV 文件 | MISSING | 报告生成器不生成 CSV |
| PDF/Word 预览 | MOCK | 固定白纸模板，不读文件 |
| 导出 Word | STUB | 固定 stub |
| 导出 PDF | STUB | 固定 stub |
| 打印 | STUB | 固定 stub |
| 删除 | PARTIAL | 后端可删但鉴权可伪造；前端不发送 x-role，正常操作 403 |
| 重新生成 | STUB | 固定 queued |
| 打开目录 | STUB | 未调用 OS shell |
| 关联数据 | MOCK | 固定会话 |
| 存储统计 | MOCK | 固定 931.5GB 等数值 |

合计：REAL 0、PARTIAL 7、MOCK 3、STUB 5、MISSING 1、UNVERIFIED 0；加权功能完成率 **29.7%**，真实实现率 **0.0%**。


## 历史记录 `/history`

| 功能 | 状态 | 依据 |
| --- | --- | --- |
| 筛选 | MOCK | 过滤 Mock 会话 |
| 分页 | MOCK | 总数固定 128 |
| 会话选择 | PARTIAL | 前端联动真实，端点数据回退 Mock |
| 时间线 | MOCK | 固定 9 节点 |
| 操作日志 | PARTIAL | 可查 operator_actions；选定会话通常无真实业务数据 |
| 文件下载 | STUB | 稳定 stub |
| 回放曲线 | PARTIAL | 路由可跳转，回放数据 Mock |
| 报告跳转 | REAL | 携带 query 跳转 |
| 趋势图 | MOCK | 固定序列 |
| Pareto | MOCK | 固定 counts/percent |
| 导出历史 | STUB | 固定 stub |
| 自动刷新 | REAL | 10/30/60s 定时并保留选择 |

合计：REAL 2、PARTIAL 3、MOCK 5、STUB 2、MISSING 0、UNVERIFIED 0；加权功能完成率 **41.2%**，真实实现率 **16.7%**。


## 系统设置 `/system-settings`

| 功能 | 状态 | 依据 |
| --- | --- | --- |
| 基础设置 | PARTIAL | 读取真实 YAML，保存到 system_settings.yaml；运行对象并非全部热更新 |
| DBC 管理 | REAL | 扫描、加载、hash、消息/信号计数 |
| 阈值编辑 | PARTIAL | Pydantic 校验和原子文件，但运行服务未全部同步 |
| 报告存储 | PARTIAL | 读取配置和真实磁盘，目录迁移未实现 |
| 权限矩阵 | MOCK | 固定角色，无认证系统 |
| 配置历史 | REAL | 写入/查询 SQLite |
| Mock | PARTIAL | 切换状态，不重建 gateway |
| 维护模式 | PARTIAL | 二次确认与后端校验存在，但无可信身份 |
| 0x123 | PARTIAL | 默认关且有 gate，无真实扩展发送实现 |
| 0x126 | PARTIAL | 默认关且 126..525 校验，无真实发送 |
| CANopen NMT | PARTIAL | 默认关且有 gate |
| 导入配置 | STUB | 无文件选择/解析 |
| 导出配置 | STUB | 返回快照但不保存文件 |
| DBC 重载 | REAL | 实际重扫 assets |
| 恢复安全默认 | PARTIAL | 关闭危险项，但身份校验不可依赖 |

合计：REAL 3、PARTIAL 9、MOCK 1、STUB 2、MISSING 0、UNVERIFIED 0；加权功能完成率 **53.0%**，真实实现率 **20.0%**。
