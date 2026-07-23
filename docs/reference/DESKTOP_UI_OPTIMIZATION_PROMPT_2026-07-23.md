# 桌面端 UI 统一优化实施 Prompt（可直接用于后续工作）

你正在维护“低速无人车线控底盘生产下线管理平台”。请基于当前仓库完成 11 个 Electron/Vue 桌面页面的 UI 一致性、中文化、响应式布局、状态稳定性和图表可读性收口。

## 开始前必须阅读

1. 根 `AGENTS.md`；
2. `docs/audit/16_DESKTOP_UI_CONSISTENCY_AUDIT_2026-07-23.md`；
3. `docs/verification/ui-consistency-audit-2026-07-23/README.md` 及 22 张截图；
4. `docs/current_audit_2026-07-20/02_DESKTOP_UI_PAGE_FUNCTION_AUDIT.md`（位于外层实施资料包时按实际路径读取）；
5. `docs/verification/ui-page-stub-closure-2026-07-22/01_PAGE_TRACEABILITY_MATRIX.md`；
6. `desktop/src/pages` 的 11 个业务页面、共享组件、styles、stores、api/types、websocket；
7. backend 的 config/channels、signals dashboard/WS publisher、EOL/alarms dashboard API 和相关测试。

开始实现前先运行 `git status --short`，逐项审查当前未提交 UI 改动，保留其意图，不覆盖用户修改。先输出问题到文件/组件/行号的实施矩阵，再修改代码。

## 安全边界

- 只使用 Mock 和 `127.0.0.1` 回环验证，不访问真实 CAN 设备或非回环 endpoint。
- 不扩大主动发送白名单；默认仍只允许 CAN2 的 `0x121`。
- 不启用 `0x123`、`0x126`、CANopen NMT 或任何新的主动发送路径。
- UI 不直接发送 CAN，所有控制继续经过后端、安全联锁、权限和操作审计。
- CAN1 的主动发送/控制权限保持锁定关闭；不能为了“开关可点击”破坏安全策略。
- 不把 Mock、stale、fallback 或 invalid 数据显示为真实新鲜数据。
- 不提交账号、token、密钥、现场 IP 或一次性初始化凭据。

## 总体目标

保持现有深蓝工业风和页面信息架构，不做无关品牌重设计。以“告警诊断”底部主要操作按钮为视觉基线，建立全站共享按钮、状态字典和响应式布局规则。所有页面必须在 1366×768、1920×1080 下完整可见，无页面级滚动；表格、列表和密集配置区可以使用明确的内部滚动。

## A. 网络配置真实控件与安全语义

1. 删除页面内只渲染 `span` 的 `ToggleVisual`，复用或完善共享 `ToggleSwitch`：
   - 使用原生 button/checkbox 或 `role="switch"`；
   - 明确 `aria-checked`、`aria-disabled`；
   - 支持鼠标、Space、Enter；
   - emit `update:modelValue`，修改页面配置草稿；
   - 有“未应用变更”标记。
2. 不得继续把后端 `ChannelConfig.enabled` 模糊显示为“发送允许”。如果后端字段语义仍是通道启用，则改名为“通道启用”，并把“主动发送权限”作为独立的安全状态展示。
3. 如果必须实现真实发送允许字段，只做最小 API 扩展并加 pydantic 类型、权限、审计和回滚：
   - CAN1 永远锁定关闭，显示“安全策略锁定：CAN1 禁止主动发送”；
   - CAN2 只允许管理员在安全策略允许范围内关闭/重新开启；
   - 不能改变 `{0x121}` 白名单。
4. 默认控制通道使用互斥 radio/segmented 控件。当前批准策略下 CAN1 不可选，CAN2 可作为唯一控制通道；服务端继续拒绝多个控制通道。
5. 所有变更只在“保存并应用”后生效，必须走后端校验、健康检查、失败回滚和审计。失败时恢复上一已应用快照，并保留明确中文错误。
6. 重做 1366 布局。不能把 4 个完整配置卡塞进固定 340 px 高度。可选方案：
   - CAN1/CAN2 配置页签 + 本机/诊断摘要；或
   - 主区域内部滚动，顶部固定通道选择和应用状态。
   关键开关、IP/端口和保存应用按钮必须可达。

## B. 信号状态稳定性

1. 修复 REST `/signals/dashboard` 与 WS `signals.dashboard` 的响应形状不一致：
   - 首选后端广播与 REST 相同的完整 response model/envelope；
   - 前端 handler 仍兼容 `payload.status.quality`，归一化到顶层 `quality`；
   - `mock/updated_at/data_source/trace_id` 也保持同形。
2. 不允许 WebSocket payload 缺字段时把已有 `good` 状态直接覆盖为 `unavailable`。
3. 定义 `good/degraded/stale/invalid/unavailable/mock` 的中文标签、颜色和数据保留规则。stale/invalid/unavailable 不参与安全判断。
4. 连续 60 秒 normal_pass 仿真中，页面不能在“正常/不可用”之间周期跳变；写自动化采样断言。
5. 把所有 `stale/unavailable/ON/OFF/Auto/Released` 等用户可见原始英文替换为统一中文字典。

## C. 灯光与制动灯效

1. `LightItem` 的点亮状态必须由信号值决定，不能由调用处静态 `active/danger` 决定。
2. 建立状态归一化函数，支持后端明确允许的 boolean、0/1、ON/OFF 值；未知值返回 unknown，不要默认 false。
3. 点亮颜色：
   - 左转灯、右转灯：黄色 `#F6C343`；
   - 位置灯：红色 `#EF4444`；
   - 近光灯：白色 `#F8FAFC`；
   - 制动请求：红色 `#EF4444`。
4. 点亮时使用静态光晕、边框和轻微背景高亮；关闭时为中性灰。不要引入持续闪烁动画。
5. stale/invalid/unavailable 时必须清除点亮效果并显示“未知/数据陈旧”，不得保留最后一次 ON 灯效。
6. 增加五种信号的 ON、OFF、stale、invalid 组件测试和页面截图断言。

## D. CAN 监控筛选器

1. 通道显示“全部/CAN1/CAN2”；方向显示“全部/接收/发送”；进制显示“十六进制/十进制”。可在辅助说明中保留 RX/TX、Hex/Dec。
2. 不复用全局固定 `min-width:70px` 导致溢出的 segmented 样式。组件按选项数等分宽度，按钮文字不得被裁切。
3. 1366 下过滤栏重排为两行或自适应 grid；所有字段必须完整显示。
4. 添加 DOM 断言：每个 segmented 子按钮的 rect 均完全位于父容器内，文本 `scrollWidth <= clientWidth + 1`。

## E. 实时曲线实时/历史模式分离

1. 删除默认会话 `EOL-20260401-0001`。
2. 实时模式只请求 curve config 和实时 timeseries，不请求 replay/fault-events。
3. 仅当 `route.query.mode === 'history'` 且存在有效 `session_id` 时加载历史接口；会话必须来自历史 API 或显式路由。
4. 无效历史会话只在回放区域显示“检测会话不存在（追踪编号：...）”，不污染实时曲线的全页状态。
5. 切换回实时模式时清理历史错误、游标、故障事件和回放元数据。
6. 测试实时模式零历史请求、合法会话成功、空 ID、404、超时和切换模式。

## F. 图表可读性和防溢出

1. 1920×1080 可以保持 2×3 曲线网格；1366×768 不得把 6 图继续压缩到不可读高度。使用分组页签、2×2 活动图表或可切换单图大视图。
2. 实时模式隐藏/折叠历史回放区，为实时图表释放高度。
3. 每张图设置最小有效绘图区高度。图例使用 `type:'scroll'` 或短中文名称；完整名称放 tooltip。
4. 使用 `containLabel`、`axisLabel.hideOverlap`、合理 interval/formatter；限制时间轴刻度数；多 Y 轴留足 right/left。
5. CAN ID 分布、实时曲线、一键检测实时图、告警图全部检查：标题、图例、坐标轴、标签不覆盖、不超出卡片。
6. 保留现有 `ResizeObserver`，避免通过固定等待或强制重建图表解决 resize。不要在后台刷新时无意义修改 chart `key`。
7. 增加 1366、1920 截图回归和图表容器边界断言。

## G. 按钮体系和 hover

1. 抽取共享组件，禁止各页继续复制大段按钮 CSS：
   - `IndustrialButton`：compact 32 px、default 36 px；
   - `IndustrialActionButton`：70 px，沿用告警诊断的图标块、主渐变和危险渐变。
2. variants 至少包括 neutral/primary/success/warning/danger；危险操作不能变成普通蓝色。
3. 所有按钮统一：7 px 圆角、边框、字体、图标尺寸、disabled、loading、focus-visible。
4. hover 必须明显高亮：亮度提升、主色边框和柔和 box-shadow，140～180 ms transition；可用按钮才响应 hover；不得通过闪烁动画实现。
5. 页面底部主要动作统一使用 70 px 组件；筛选和标题栏保持 compact，不要把所有按钮强制放大。
6. 补充 hover/focus/disabled/permission-denied 的组件测试。

## H. 消除后台刷新导致的按钮闪烁

1. stores 拆分：`initialLoading`、`refreshing`、`actionPending`、`error`；不要让背景刷新复用写操作 pending。
2. 页面按钮只因业务前置条件、权限或对应 actionPending 禁用，不因定时刷新禁用。
3. 告警和 EOL 的 WebSocket 事件优先增量更新 store；确需 GET 时使用 leading/trailing throttle、请求合并和并发去重。
4. `PageDataState` 使用固定尺寸状态槽；背景刷新用不改变布局的细小指示器，不能反复插入/删除导致标题和按钮位移。
5. 运行中检测和持续告警各采样 60 秒，断言主要按钮 DOM 节点不被替换，disabled/opacity 不因背景刷新改变。

## I. 响应式布局

1. 修复总览和网络配置在 1366 下页面根节点超出 `.content` 的问题。
2. 修复手动控制约 89 px、一键检测约 79 px 的 1920 底部空白；将一个或多个内容区改为 `minmax(0,1fr)`，让图表/列表吸收剩余空间。
3. 所有页面 E2E 同时断言：
   - document 不产生页面级滚动；
   - page rect 完全位于 content rect；
   - 一级 section 不被 viewport 裁切；
   - 内部 scroll 容器能滚到首尾；
   - 页面底部空白不超过设计间距 12～16 px。
4. 不使用 `overflow:hidden` 掩盖尺寸错误。

## J. 全站中文化

建立唯一 `uiStatusLabels.ts` 或等价映射，并在 11 页复用：

- online/offline → 在线/离线；
- unavailable/stale/invalid → 不可用/数据陈旧/无效；
- Normal/Warning/Fault/Critical → 正常/警告/故障/严重；
- PASS/FAIL/RUNNING/ABORTED/WAIT/PAUSED → 通过/失败/运行中/已中止/等待/已暂停；
- admin/operator/engineer/viewer → 管理员/操作员/工程师/查看者；
- Manual/Remote/Auto → 手动/远程/自动；
- ON/OFF/RELEASED/enabled/disabled → 开启/关闭/已释放/已启用/已禁用；
- trace → 追踪编号。

CAN、DBC、BMS、VIN、SOC、UDP、TCP、PDF、CSV 等标准缩写允许保留，但使用中文优先标签，例如“车辆识别码（VIN）”“十六进制（Hex）”。增加静态测试，禁止批准词典之外的原始英文状态进入用户可见模板。

## K. 11 页逐页验收

每页至少增加：

- 1366×768 和 1920×1080 的边界/布局断言；
- 一个统一按钮组件断言；
- 一个中文状态断言；
- 一个 loading/error/stale/permission-denied 不跳布局的断言；
- 有图表的页面增加 chart 容器和标签策略断言；
- 涉及实时数据的页面增加 10～60 秒稳定性采样。

页面专项验收：

- 总览：最近会话可达，无裁切；
- Network：安全开关有真实草稿交互、回滚和锁定原因；
- CAN：所有筛选项完整可见；
- Signals：60 秒不抖动，五个灯效正确；
- Curves：实时模式零历史请求，无文字重叠；
- Manual：铺满窗口，联锁和 fail-closed 不变；
- Auto Test：铺满窗口，运行时按钮不闪；
- Alarms：作为按钮视觉基线，刷新不闪；
- Reports：打印/导出/删除按钮层级统一；
- History：状态和筛选中文化；
- Settings：角色、Mock、危险功能中文化且危险性不弱化。

## 测试与验证

只使用临时目录、Mock 和回环：

```powershell
cd desktop
npm.cmd run lint
npm.cmd run test
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:bundle
npm.cmd run test:e2e
```

同时运行相关后端 signals/config/EOL/alarms 测试。若修改 API 模型，运行后端全部测试并重新生成 OpenAPI 类型/文档。不得执行真实硬件测试。

Electron E2E 必须覆盖 11 页、两种分辨率，并增加：

1. 运行态信号连续 60 秒质量稳定；
2. Network 草稿切换、保存应用、失败回滚、安全锁定；
3. CAN 筛选器完整可见并可操作；
4. 实时曲线不请求虚构会话；
5. 一键检测和告警页按钮在背景刷新时不闪烁；
6. 灯光五种状态和 stale/invalid；
7. 页面 rect、一级 section、内部滚动和底部空白阈值；
8. 图表边界和截图回归；
9. 401/403、offline、stale 和 simulator 停止后的控制 409。

## 交付

- 实现代码、测试和必要的最小 API 类型变更；
- 更新 UI、API、WebSocket、配置和测试文档；
- 在 `docs/verification` 新增本工作包证据，记录 commit、命令、结果、22 页截图对比、60 秒稳定性指标和回环边界；
- 更新 `docs/20_risk_and_open_questions.md`；
- 最终列出改动文件、关键 UI/安全决策、测试结果和仍需 Windows 工控机确认的事项；
- 不提交真实凭据、现场地址或测试生成的 session token。

## 完成判定

不能只以“页面能打开、没有滚动条、按钮有 Toast、截图生成成功”判定完成。必须证明内容未裁切、控件真实可用、状态不抖动、中文化完整、图表可读、权限与安全边界保持不变。
