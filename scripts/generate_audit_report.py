from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "audit"
EVIDENCE = AUDIT / "evidence"
AUDIT_TIME = "2026-07-10 12:30:00 +08:00"
PROJECT_VERSION = "1.0.2"


def write(name: str, content: str) -> None:
    path = AUDIT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", "<br>")

    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(cell(value) for value in row) + " |" for row in rows),
        ]
    )


visual_pages = [
    {
        "id": "01",
        "route": "/overview",
        "name": "总览工作台",
        "score": 91,
        "parts": [28, 19, 14, 14, 8, 5, 3],
        "mad": 22.366,
        "changed": 39.333,
        "priority": "P2",
        "gaps": "状态卡与图表区比参考图更紧凑；顶部状态的新开页初始化偶发显示 CAN 离线；若数据库为空，多数业务指标来自 fallback。",
        "missing": "没有真实数据库产能统计；最近会话为 fallback。",
        "extra": "自定义无框标题栏占用 32px，参考图没有独立评估该高度。",
        "w1920": "一屏显示，document 1080px，无页面级滚动；无 Failed to fetch 横幅。",
        "w1366": "页面根内容约 814px，高于约 610px 可用区且 overflow 隐藏，底部内容存在裁切。",
    },
    {
        "id": "02",
        "route": "/network-config",
        "name": "网络配置",
        "score": 90,
        "parts": [27, 19, 14, 14, 8, 5, 3],
        "mad": 19.428,
        "changed": 31.297,
        "priority": "P2",
        "gaps": "四卡结构接近参考图，但诊断数值均为 Stub；TCP 可选但后端只有 UDP gateway。",
        "missing": "真实 Ping、回环、协议合法率、DLC/保留位诊断。",
        "extra": "Mock 状态提示是当前实现新增的必要降级信息。",
        "w1920": "一屏显示，无页面级滚动。",
        "w1366": "页面根内容约 852px，发生隐藏裁切。",
    },
    {
        "id": "03",
        "route": "/can-monitor",
        "name": "CAN 报文监控",
        "score": 84,
        "parts": [25, 17, 12, 13, 8, 5, 4],
        "mad": 22.140,
        "changed": 36.030,
        "priority": "P1",
        "gaps": "主表和详情位置正确，但详情信号及底部统计由固定数据生成，不是实时 DBC 解码结果；同 ID 跨通道被合并。",
        "missing": "真实导出、历史文件、实时统计、按实际帧值解码详情。",
        "extra": "帧更新次数列增加了可观测性。",
        "w1920": "一屏显示，表格内部滚动正常。",
        "w1366": "主要结构仍能放入可用区，是兼容性较好的页面之一。",
    },
    {
        "id": "04",
        "route": "/signal-dashboard",
        "name": "信号仪表盘",
        "score": 83,
        "parts": [25, 17, 12, 13, 7, 5, 4],
        "mad": 18.743,
        "changed": 28.680,
        "priority": "P2",
        "gaps": "卡片矩阵、底盘示意和 Watchlist 基本齐全；趋势与缺失信号大量回填固定值，实时/Mock 边界不清楚。",
        "missing": "真实布局保存和真实关注信号持久化。",
        "extra": "页面级离线徽标。",
        "w1920": "一屏显示。",
        "w1366": "核心结构可见，密度明显高于参考图但未发现页面级滚动。",
    },
    {
        "id": "05",
        "route": "/realtime-curve",
        "name": "实时曲线",
        "score": 84,
        "parts": [25, 17, 13, 13, 7, 5, 4],
        "mad": 19.724,
        "changed": 37.315,
        "priority": "P1",
        "gaps": "六图矩阵完整，但页面显示 0/256 已选时曲线仍全部存在；采样、降采样和历史回放多为 UI/Mock。",
        "missing": "选择信号对 series 的真实约束、真实 CSV/快照、回放 seek。",
        "extra": "离线曲线状态徽标。",
        "w1920": "一屏显示，图表均非空。",
        "w1366": "根 scrollHeight 约 764px、clientHeight 约 610px且隐藏，底部回放区裁切。",
    },
    {
        "id": "06",
        "route": "/manual-control",
        "name": "手动控制",
        "score": 89,
        "parts": [27, 18, 14, 14, 8, 5, 3],
        "mad": 21.886,
        "changed": 38.830,
        "priority": "P0",
        "gaps": "视觉结构接近参考，但控制状态卡使用硬编码 allow；页面预览字节与实际发帧不一致。",
        "missing": "真实反馈和曲线、可证明的停车闭环。",
        "extra": "4 个控件计算样式为白底，破坏统一深色表单。",
        "w1920": "一屏显示。",
        "w1366": "根内容约 906px，明显裁切。",
    },
    {
        "id": "07",
        "route": "/auto-test",
        "name": "一键检测",
        "score": 87,
        "parts": [27, 18, 13, 14, 8, 5, 2],
        "mad": 24.030,
        "changed": 38.302,
        "priority": "P0",
        "gaps": "12 步和高密度区域基本还原，但 dashboard 展示固定会话；运行引擎与 UI 状态没有真实闭环。",
        "missing": "真实测量/断言/日志/曲线持久化，可靠暂停、中止和急停。",
        "extra": "Mock 会话状态可与实际引擎状态并存。",
        "w1920": "一屏显示。",
        "w1366": "根内容约 893px，底部按钮与统计区裁切。",
    },
    {
        "id": "08",
        "route": "/alarm-diagnosis",
        "name": "告警诊断",
        "score": 88,
        "parts": [27, 18, 14, 14, 8, 5, 2],
        "mad": 21.049,
        "changed": 39.375,
        "priority": "P1",
        "gaps": "0x77、0x102 和 bitmap 布局完整，但历史、建议、图表和多数详情来自 Mock。",
        "missing": "真实诊断导出、人工放行工作流、告警持久化。",
        "extra": "跳转前先调用 Stub API。",
        "w1920": "一屏显示。",
        "w1366": "根内容约 762px，底部区域裁切。",
    },
    {
        "id": "09",
        "route": "/report-management",
        "name": "报告管理",
        "score": 86,
        "parts": [26, 18, 13, 14, 8, 5, 2],
        "mad": 25.333,
        "changed": 39.951,
        "priority": "P1",
        "gaps": "报告预览器视觉完整，但并未打开真实 PDF/DOCX；操作按钮多为 Stub，删除请求不携带角色头。",
        "missing": "真实预览、打印、导出、重新生成、目录打开。",
        "extra": "Mock 预览纸张在任意文件类型下均可显示。",
        "w1920": "一屏显示。",
        "w1366": "页面改为内部 overflow:auto，需要页面滚动才能看完，不满足一屏要求。",
    },
    {
        "id": "10",
        "route": "/history",
        "name": "历史记录",
        "score": 89,
        "parts": [27, 19, 14, 14, 8, 5, 2],
        "mad": 20.979,
        "changed": 38.894,
        "priority": "P1",
        "gaps": "两栏时间线、下载卡、Pareto 和分页均接近参考图，但数据库无业务记录，展示源是 Mock。",
        "missing": "真实会话、时间线、文件下载和历史导出。",
        "extra": "自动刷新控件为当前实现补充。",
        "w1920": "一屏显示。",
        "w1366": "页面内部滚动，底部统计无法同时可见。",
    },
    {
        "id": "11",
        "route": "/system-settings",
        "name": "系统设置",
        "score": 86,
        "parts": [26, 18, 13, 14, 8, 5, 2],
        "mad": None,
        "changed": None,
        "priority": "P1",
        "gaps": "按需求文档形成三行网格与七按钮，但角色矩阵没有认证支撑，维护模式只保存进程内状态。",
        "missing": "真实文件选择/导入/导出、身份认证、生产配置发布闭环。",
        "extra": "系统设置没有独立参考图，使用统一风格与 11_system_settings.md 评估。",
        "w1920": "一屏显示。",
        "w1366": "使用页面内部滚动，不能同时显示全部卡片和底部按钮。",
    },
]


function_pages: list[dict[str, Any]] = [
    {
        "route": "/overview", "name": "总览", "functions": [
            ("KPI 数据来源", "PARTIAL", "API 混合 SQLite 结果和 fallback；数据库无会话记录"),
            ("CAN1/CAN2 状态", "PARTIAL", "读取真实 gateway，但 fps 算法和顶部状态存在不一致"),
            ("当前车辆", "MOCK", "固定 YL-JD-001"),
            ("告警摘要", "PARTIAL", "最高等级可来自 SignalStore，其余保护项固定"),
            ("快捷入口", "PARTIAL", "路由可用，打开目录为 Stub，安全停车仅部分实现"),
            ("今日结果图", "MOCK", "固定 18/17/1"),
            ("小时产能图", "MOCK", "固定序列"),
            ("帧率趋势", "MOCK", "固定趋势"),
            ("最近会话", "MOCK", "数据库为空后回填固定会话"),
            ("安全停车快捷按钮", "PARTIAL", "调用后端，但只发一次停车帧"),
        ]},
    {
        "route": "/network-config", "name": "网络配置", "functions": [
            ("读取配置", "PARTIAL", "返回运行配置与固定 NIC 信息"), ("保存配置", "PARTIAL", "校验并更新配置结构，运行 gateway 不支持完整热切换/持久化闭环"),
            ("UDP/TCP 切换", "PARTIAL", "UI/API 接受 TCP，实际仅有 UdpCanGateway"), ("CAN1 启停", "REAL", "实际绑定/关闭 socket"),
            ("CAN2 启停", "REAL", "实际绑定/关闭 socket"), ("自检", "STUB", "self-test 明确 stub=true"),
            ("Ping", "MOCK", "固定 0.92ms"), ("UDP 回环", "MOCK", "固定 pass"), ("13 字节合法率", "MOCK", "固定 99.96%"),
            ("DLC/保留位校验", "MOCK", "协议 codec 有校验，但诊断接口不执行测试"), ("粘包/半包统计", "MOCK", "固定 0/0"),
            ("恢复默认", "PARTIAL", "接口可恢复默认对象，未证明 gateway 原子重连"), ("端口检测", "PARTIAL", "状态主要来自固定配置"),
        ]},
    {
        "route": "/can-monitor", "name": "CAN 监控", "functions": [
            ("按 CAN ID 聚合", "REAL", "后端 latest map + 前端 Record"), ("新帧 upsert", "REAL", "同 ID 更新对应行"),
            ("CAN ID 排序", "REAL", "三态排序"), ("行选择", "REAL", "选中 ID 联动请求详情"),
            ("详情解码", "PARTIAL", "框架联动真实，signals 内容对常用 ID 硬编码"), ("0x77 详情", "MOCK", "固定 Normal 信号"),
            ("0x121 详情", "MOCK", "固定示例数据"), ("暂停刷新", "REAL", "pending map 暂存后 flush"),
            ("过滤", "REAL", "通道/ID/报文名/方向/状态"), ("导出 CSV", "STUB", "后端 stub"),
            ("原始日志导出", "STUB", "后端 stub"), ("历史文件", "MOCK", "固定文件清单"),
            ("统计图", "MOCK", "固定分布、趋势、抖动和错误数"),
        ]},
    {
        "route": "/signal-dashboard", "name": "信号仪表盘", "functions": [
            ("BMS", "PARTIAL", "SignalStore 覆盖部分字段，其余 fallback"), ("车辆状态", "PARTIAL", "部分真实信号 + fallback"),
            ("四轮轮速", "PARTIAL", "可读解码值，单位/映射仍有限"), ("转向反馈", "PARTIAL", "实时反馈可覆盖"),
            ("电机转速", "PARTIAL", "缺失时回填"), ("电机相电流", "PARTIAL", "文案单位 A 正确，数据源不完整"),
            ("心跳", "PARTIAL", "收到 0x703/0x704 可更新"), ("灯光", "PARTIAL", "部分信号/回填"),
            ("制动", "PARTIAL", "部分信号/回填"), ("告警", "PARTIAL", "SignalStore 最高等级"),
            ("Watchlist", "MOCK", "固定 8 行，少量值覆盖"), ("趋势图", "MOCK", "固定 sparkline"),
            ("自定义布局", "STUB", "按钮有反馈，无布局引擎"), ("保存关注信号", "STUB", "后端接口明确 stub"),
        ]},
    {
        "route": "/realtime-curve", "name": "实时曲线", "functions": [
            ("信号分组", "MOCK", "固定 group/config"), ("信号勾选", "PARTIAL", "checkbox 状态未约束实际 series"),
            ("6 个图表", "MOCK", "ECharts 真实渲染，数据固定"), ("时间窗口", "PARTIAL", "可改查询参数，后端忽略部分语义"),
            ("采样率", "PARTIAL", "控件与 query 存在，未执行真实重采样"), ("降采样", "MOCK", "选项存在，无算法"),
            ("暂停/继续", "PARTIAL", "轮询可暂停，WebSocket handler 仍触发加载"), ("缩放复位", "PARTIAL", "本地图表操作"),
            ("CSV", "STUB", "后端 stub"), ("快照", "STUB", "后端 stub"),
            ("历史会话", "MOCK", "固定回放元数据"), ("播放控制", "PARTIAL", "本地游标，seek 未形成后端闭环"),
            ("故障跳转", "PARTIAL", "固定故障事件与本地跳转"),
        ]},
    {
        "route": "/manual-control", "name": "手动控制", "functions": [
            ("安全联锁", "PARTIAL", "实际发送会 evaluate；展示接口却硬编码 allow"), ("档位", "REAL", "进入真实 0x121 payload"),
            ("驱动模式", "REAL", "进入真实 payload"), ("目标速度", "REAL", "0.1km/h 编码并受限速阻断"),
            ("前后转角", "REAL", "真实 int8 编码"), ("制动", "REAL", "进入 payload"), ("灯光", "REAL", "进入 payload"),
            ("0x121 预览", "PARTIAL", "API 返回真实 data，但 UI bytes_hex 采用另一套字节排列/比例"),
            ("int8 补码", "REAL", "-120/-60/0/60/120 实测正确"), ("一次发送", "REAL", "回环仿真器收到"),
            ("周期发送", "REAL", "回环仿真器收到"), ("停止发送", "REAL", "scheduler task 停止"),
            ("安全停车", "PARTIAL", "只发送一次 N/0/制动帧"), ("急停", "PARTIAL", "停止周期并锁存，但不下发停车帧"),
            ("解除急停", "PARTIAL", "仅清布尔锁存，无静止/反馈复核"), ("实时反馈", "MOCK", "固定 API"), ("曲线", "MOCK", "固定 API"),
        ]},
    {
        "route": "/auto-test", "name": "一键检测", "functions": [
            ("会话创建", "PARTIAL", "创建内存会话，不落库"), ("12 步流程", "PARTIAL", "存在 12 名称但不执行对应动作"),
            ("开始", "PARTIAL", "启动简化异步循环"), ("暂停", "PARTIAL", "状态改 PAUSED，任务继续"),
            ("继续", "PARTIAL", "状态接口存在，无真正阻塞点"), ("中止", "PARTIAL", "ABORTED 被最终 PASS 覆盖"),
            ("急停", "PARTIAL", "设置锁存但测试任务继续并 PASS"), ("当前测量值", "MOCK", "dashboard 固定"),
            ("检测断言", "PARTIAL", "引擎仅检查严重告警/SOC，页面断言固定"), ("步骤日志", "MOCK", "dashboard 固定"),
            ("曲线", "MOCK", "固定序列"), ("PASS/FAIL", "PARTIAL", "转向/制动故障错误 PASS"),
            ("报告生成", "PARTIAL", "生成文件但内容损坏/不完整"), ("数据持久化", "MISSING", "核心业务表 0 行"),
        ]},
    {
        "route": "/alarm-diagnosis", "name": "告警诊断", "functions": [
            ("0x77 矩阵", "PARTIAL", "部分 SignalStore 值覆盖固定矩阵"), ("0x102 unsigned bool", "PARTIAL", "bitmap unsigned 正确，单项保护值不完整"),
            ("Bitmap", "PARTIAL", "真实 16bit 数值可显示"), ("当前告警", "PARTIAL", "内存告警服务"),
            ("历史告警", "MOCK", "固定 5 条"), ("诊断建议", "MOCK", "固定建议"),
            ("人工放行", "STUB", "固定 stub"), ("确认告警", "PARTIAL", "可对内存项 ack"),
            ("跳转 CAN 帧", "PARTIAL", "API stub 后前端路由跳转"), ("导出诊断", "STUB", "固定 stub"),
            ("安全停车", "PARTIAL", "调用不完整 safe-stop"),
        ]},
    {
        "route": "/report-management", "name": "报告管理", "functions": [
            ("扫描目录", "PARTIAL", "确实扫描 data/reports，但响应仍标 stub"), ("报告列表", "PARTIAL", "扫描结果与 Mock 混合"),
            ("筛选", "PARTIAL", "对当前混合列表服务端过滤"), ("Word 文件", "PARTIAL", "实际生成 DOCX，但内容乱码"),
            ("PDF 文件", "PARTIAL", "实际生成 PDF，但中文方块且内容不足"), ("JSON 文件", "PARTIAL", "可打开但缺版本/hash"),
            ("CSV 文件", "MISSING", "报告生成器不生成 CSV"), ("PDF/Word 预览", "MOCK", "固定白纸模板，不读文件"),
            ("导出 Word", "STUB", "固定 stub"), ("导出 PDF", "STUB", "固定 stub"), ("打印", "STUB", "固定 stub"),
            ("删除", "PARTIAL", "后端可删但鉴权可伪造；前端不发送 x-role，正常操作 403"),
            ("重新生成", "STUB", "固定 queued"), ("打开目录", "STUB", "未调用 OS shell"),
            ("关联数据", "MOCK", "固定会话"), ("存储统计", "MOCK", "固定 931.5GB 等数值"),
        ]},
    {
        "route": "/history", "name": "历史记录", "functions": [
            ("筛选", "MOCK", "过滤 Mock 会话"), ("分页", "MOCK", "总数固定 128"),
            ("会话选择", "PARTIAL", "前端联动真实，端点数据回退 Mock"), ("时间线", "MOCK", "固定 9 节点"),
            ("操作日志", "PARTIAL", "可查 operator_actions；选定会话通常无真实业务数据"), ("文件下载", "STUB", "稳定 stub"),
            ("回放曲线", "PARTIAL", "路由可跳转，回放数据 Mock"), ("报告跳转", "REAL", "携带 query 跳转"),
            ("趋势图", "MOCK", "固定序列"), ("Pareto", "MOCK", "固定 counts/percent"),
            ("导出历史", "STUB", "固定 stub"), ("自动刷新", "REAL", "10/30/60s 定时并保留选择"),
        ]},
    {
        "route": "/system-settings", "name": "系统设置", "functions": [
            ("基础设置", "PARTIAL", "读取真实 YAML，保存到 system_settings.yaml；运行对象并非全部热更新"),
            ("DBC 管理", "REAL", "扫描、加载、hash、消息/信号计数"), ("阈值编辑", "PARTIAL", "Pydantic 校验和原子文件，但运行服务未全部同步"),
            ("报告存储", "PARTIAL", "读取配置和真实磁盘，目录迁移未实现"), ("权限矩阵", "MOCK", "固定角色，无认证系统"),
            ("配置历史", "REAL", "写入/查询 SQLite"), ("Mock", "PARTIAL", "切换状态，不重建 gateway"),
            ("维护模式", "PARTIAL", "二次确认与后端校验存在，但无可信身份"), ("0x123", "PARTIAL", "默认关且有 gate，无真实扩展发送实现"),
            ("0x126", "PARTIAL", "默认关且 126..525 校验，无真实发送"), ("CANopen NMT", "PARTIAL", "默认关且有 gate"),
            ("导入配置", "STUB", "无文件选择/解析"), ("导出配置", "STUB", "返回快照但不保存文件"),
            ("DBC 重载", "REAL", "实际重扫 assets"), ("恢复安全默认", "PARTIAL", "关闭危险项，但身份校验不可依赖"),
        ]},
]


def function_metrics(page: dict[str, Any]) -> dict[str, Any]:
    counts = Counter(status for _, status, _ in page["functions"])
    total = len(page["functions"])
    weighted = (
        counts["REAL"]
        + 0.5 * counts["PARTIAL"]
        + 0.25 * counts["MOCK"]
        + 0.1 * counts["STUB"]
    )
    return {
        "total": total,
        **{key.lower(): counts[key] for key in ("REAL", "PARTIAL", "MOCK", "STUB", "MISSING", "UNVERIFIED")},
        "functional_completion": round(weighted / total * 100, 1),
        "real_completion": round(counts["REAL"] / total * 100, 1),
    }


for page in function_pages:
    page["metrics"] = function_metrics(page)

all_function_counts = Counter()
for page in function_pages:
    for _, status, _ in page["functions"]:
        all_function_counts[status] += 1
function_total = sum(all_function_counts.values())
functional_completion = round(
    (all_function_counts["REAL"] + 0.5 * all_function_counts["PARTIAL"] + 0.25 * all_function_counts["MOCK"] + 0.1 * all_function_counts["STUB"])
    / function_total
    * 100,
    1,
)
real_completion = round(all_function_counts["REAL"] / function_total * 100, 1)


def issue(
    issue_id: str,
    severity: str,
    category: str,
    module: str,
    title: str,
    phenomenon: str,
    impact: str,
    evidence: str,
    code: str,
    fix: str,
    effort: str,
    safety: bool = False,
    block: bool = False,
    cause: str = "实现停留在演示/最小闭环，缺少生产约束。",
    dependency: str = "无",
) -> dict[str, Any]:
    return {
        "issue_id": issue_id,
        "category": category,
        "module": module,
        "severity": severity,
        "title": title,
        "phenomenon": phenomenon,
        "impact": impact,
        "reproduction": "按证据文件中的命令或脚本执行并对比记录字段。",
        "evidence": evidence,
        "code": code,
        "cause": cause,
        "recommendation": fix,
        "effort": effort,
        "dependencies": dependency,
        "status": "OPEN",
        "blocks_production": "是" if block else "否",
        "vehicle_safety": "是" if safety else "否",
    }


issues = [
    issue("SAFE-001", "P0", "安全", "EOL 状态机", "暂停、中止和急停不停止 EOL 执行任务", "pause 后步骤从 3 增至 8；abort/emergency 最终均被覆盖为 PASS。", "操作员无法可靠停止车辆相关检测流程。", "evidence/tests/eol_state_machine.json", "backend/app/eol/engine.py:24,54-65; backend/app/api/eol.py:163-195", "为每个会话持有 task/cancel token；所有步骤前后检查状态；急停先执行安全停车并等待确认。", "L", True, True),
    issue("SAFE-002", "P0", "安全", "EOL/联锁", "CAN1/CAN2 断开时一键检测仍 PASS", "审计停止两个通道后启动会话，12 步全部 PASS。", "可对无反馈车辆生成错误 PASS 结论。", "evidence/tests/eol_state_machine.json", "backend/app/eol/engine.py:29-49", "每步使用 SafetyInterlockService 和关键帧时效；断链立即失败并安全停车。", "L", True, True),
    issue("SAFE-003", "P0", "安全", "CAN/联锁", "高负载积压帧使设备断开后仍被判在线并允许控制", "55Hz profile 停止 5 秒后 CAN2 仍 online，send-once 返回 200。", "断线车辆可能在错误在线状态下接受控制。", "evidence/tests/stale_online_interlock_after_5s.txt", "backend/app/can_gateway/udp_gateway.py:49-53; backend/app/services/lifecycle.py:16-28; backend/app/can_gateway/statistics.py:35-49", "使用有界队列、接收时间戳而非处理时间、丢弃过期帧；联锁校验 source receive age。", "L", True, True),
    issue("SAFE-004", "P0", "安全/权限", "认证授权", "后端无认证且默认角色为 admin", "无凭据可进入维护模式；伪造 x-role:admin 删除不存在报告返回 200；OpenAPI 无 security scheme。", "任何可访问端口的进程可操作控制、维护和删除接口。", "evidence/api/security_probe.json", "backend/app/services/app_state.py:8; backend/app/api/config.py:472-475; backend/app/api/reports.py:261-273; backend/app/main.py:12", "实现认证会话、服务端 RBAC、不可伪造身份和最小权限；控制接口限制本机可信 IPC/令牌。", "L", True, True),
    issue("SAFE-005", "P0", "安全", "急停", "急停只停止周期任务并置位，不下发零速/制动帧", "接口响应称急停完成，但代码无 safe_stop_command 发送或反馈确认。", "车辆可能保留最后控制命令，停止周期发送不等于停车。", "evidence/simulation/control_loopback_e2e.json", "backend/app/api/control.py:157-169", "急停采用独立高优先队列，重复发送零速+制动直到反馈确认或超时，并保持锁存。", "M", True, True),

    issue("EOL-001", "P1", "检测", "故障判定", "转向无响应和制动失败 profile 错误 PASS", "steering_no_response 与 brake_fail 均完成 12 步并生成 PASS。", "生产可能放行故障底盘。", "evidence/simulation/steering_no_response_eol_result.json; evidence/simulation/brake_fail_eol_result.json", "backend/app/eol/engine.py:29-49", "按 test_plan 执行真实刺激/反馈断言，覆盖转向跟随与制动停止。", "L", True, True),
    issue("EOL-002", "P1", "检测", "步骤语义", "低 SOC/告警在第 1 步失败且引擎忽略测试计划", "bms_low_soc 和 warning_fault 仅执行 1 步；DEFAULT_STEPS 只提供名称。", "失败步骤与报告诊断结论错误。", "evidence/simulation/bms_low_soc_eol_result.json; evidence/simulation/warning_fault_eol_result.json", "backend/app/eol/engine.py:5,29-49; configs/test_plan.yaml", "加载计划模型，为每步定义 command、采样窗口、断言和失败策略。", "L", True, True),
    issue("SAFE-006", "P1", "安全/UI", "手动控制", "UI 0x121 Byte 预览与实际发送 payload 不一致", "preview 的 bytes_hex 字段排列/0.25 比例与 data、仿真器收到的真实 0.1 比例 payload 不同。", "操作员看到的待发内容不是实际报文。", "evidence/simulation/control_loopback_e2e.json", "backend/app/api/control.py:38-61; backend/app/control/control_121.py:37-52", "只返回编码器产生的一份 authoritative bytes；字段说明从同一 bytes 解码生成。", "M", True, True),
    issue("SAFE-007", "P1", "安全/UI", "手动控制", "联锁展示接口固定显示允许发送", "interlock-status 不调用 SafetyInterlockService，control/status 仅检查急停。", "UI 可在实际禁止时显示允许，误导操作员。", "evidence/api/get__control__interlock-status.json", "backend/app/api/control.py:65-79,95-112", "两个状态接口直接返回 SafetyInterlockService.evaluate 结果和阻断原因。", "S", True, True),
    issue("SAFE-008", "P1", "安全", "安全停车", "安全停车仅发送一次且不验证车辆停止", "stop scheduler 后只 send_once safe_stop_command。", "UDP 丢包或反馈异常时无法保证停车。", "evidence/simulation/control_loopback_e2e.json", "backend/app/api/control.py:147-155; backend/app/control/safe_stop.py:3-4", "实现超时状态机、周期重发、速度/制动反馈断言和审计。", "M", True, True),
    issue("PERF-001", "P1", "性能", "CAN 接收", "目标约 1045fps 时实际仅处理 345.9fps并形成长尾积压", "60 秒后模拟器停止，日志继续增长且在线状态延迟。", "实时性和安全超时失真，长时间运行会耗尽资源。", "evidence/tests/stress_1000fps_60s_summary.json; evidence/tests/post_stress_backlog_summary.txt", "backend/app/can_gateway/udp_gateway.py:49-53; backend/app/services/lifecycle.py:16-28", "引入有界队列、批处理日志、主题节流和负载丢弃策略。", "L", True, True),
    issue("API-001", "P1", "API/WebSocket", "实时推送", "每帧顺序广播 7 个大 topic，前端每次 timeseries 又发 HTTP", "3 秒收到 5,292 消息；7 个主要 topic 各 744 条。", "网络/CPU 被放大，导致积压与页面抖动。", "evidence/api/websocket_probe.json", "backend/app/services/lifecycle.py:16-28; desktop/src/stores/signals.ts:75-80", "按规范节流：raw 可选、signals 10Hz、statistics 1Hz；timeseries 直接消费 payload。", "M", False, True),
    issue("DB-001", "P1", "数据", "持久化", "EOL/CAN/信号/告警/报告核心表均为 0 行", "运行五个 profile 和控制联调后，只有 operator_actions/config_history 有数据。", "历史追溯、报告关联和审计结论不可依赖。", "evidence/tests/database_audit.json", "backend/app/eol/engine.py; backend/app/services/lifecycle.py; backend/app/reports/generator.py", "建立 session UoW，落库 steps/assertions/frames/signals/alarms/reports，并增加回滚测试。", "L", False, True),
    issue("REPORT-001", "P1", "报告", "生成器", "生成的 DOCX 中文乱码，PDF 中文方块且仅含会话/结果", "PASS/FAIL 文件可打开但内容不可用，且缺 software/DBC/config 版本。", "报告无法交付生产或审计。", "evidence/tests/report_validation.json; evidence/screenshots/current/generated_normal_pass_report_page1.png", "backend/app/reports/generator.py:10-39", "统一 UTF-8 源文本和嵌入中文字体，按模板写完整步骤/断言/版本并回归渲染。", "L", False, True),
    issue("DEPLOY-001", "P1", "部署", "Electron", "electron:build 只执行 Vite，main.cjs 生产仍加载 5173且不拉起后端", "没有 installer、Python runtime、dist load、健康等待或进程托管。", "离线工控机无法按生产方式启动。", "evidence/commands/electron_runtime_probe.json; evidence/tests/electron_build_exit.txt", "desktop/package.json:7-13; desktop/electron/main.cjs:21", "引入 electron-builder/forge，生产 loadFile(dist)，打包/拉起后端并管理生命周期。", "L", False, True),
    issue("SIM-001", "P1", "仿真", "开发配置", "默认发送地址是 [REDACTED_CAN1_GATEWAY]/99:1234，与仿真器 127.0.0.1:12341/2 不匹配", "接收绑定失败会回退 loopback，但发送地址不会同步回退。", "默认开发命令无法完成双向控制联调，且可能向真实网段发包。", "evidence/simulation/loopback_stack_startup.txt; evidence/simulation/channels.dev.audit.yaml", "configs/channels.yaml; backend/app/can_gateway/udp_gateway.py:29-44,59-65", "明确 dev/production profile，仿真启动必须显式加载 loopback 配置并阻止生产 IP。", "M", True, True),
    issue("DB-002", "P1", "日志", "原始 CAN", "所有帧同步追加到单个 raw_can_current.csv，无轮转/容量上限", "审计时文件约 119MB；每帧 open/write/close。", "高帧率下阻塞事件循环并可能耗尽磁盘。", "evidence/tests/database_audit.json", "backend/app/storage/raw_log_writer.py:8-16", "异步批量 writer、按会话/大小轮转、压缩、保留策略和磁盘阈值。", "M", False, True),

    issue("DBC-001", "P2", "协议", "USR-CAN115", "UDP 半包跨数据报拼接且没有重同步", "5 字节截断包与下一完整包拼出 parse_status=ok 的伪 0x121，真实 0x77 丢失。", "错误帧可能进入信号与告警逻辑。", "evidence/tests/protocol_probe.json", "backend/app/can_gateway/usr_can115.py:57-64; backend/app/can_gateway/udp_gateway.py:47-53", "UDP 按 datagram 校验 13*n；非法长度整包拒绝。TCP 才使用带同步策略的 stream buffer。", "M", True, True),
    issue("CAN-001", "P2", "CAN", "统计", "fps 使用启动以来累计平均而非滚动窗口", "压力结束显示 34.7/66.4fps，而 60 秒区间处理总量约 345.9fps。", "UI、超时和容量判断失真。", "evidence/tests/stress_1000fps_60s_summary.json", "backend/app/can_gateway/statistics.py:35-49", "使用 1s/5s 滚动窗口和单调时钟。", "S"),
    issue("CAN-002", "P2", "CAN", "缓存", "recent_frames 仅 2,000 帧，低于资料包每通道至少 10,000 建议", "约 1000fps 时只保留约 2 秒且两通道共享。", "诊断回看与短时统计不足。", "evidence/tests/protocol_probe.json", "backend/app/can_gateway/manager.py:12", "按通道有界环形缓存，容量配置化并监控使用率。", "S"),
    issue("DBC-002", "P2", "DBC", "0x102", "运行解码只产生总 bitmap，监控详情中的保护位为固定数据", "protocol probe 只得到 BMS_Protect_Bitmap=32769。", "实际单项保护状态可能与 UI 不一致。", "evidence/tests/protocol_probe.json", "backend/app/dbc/service.py:89-91; backend/app/api/can.py:256-267", "按 override 显式输出 unsigned bool/bitmap 信号，并用当前帧值构造详情。", "M", True),
    issue("API-002", "P2", "API", "Dashboard", "大量固定数据返回 200 且未统一标识 Mock", "统计、历史、曲线等可看似真实；只有部分 dashboard 有 mock 字段。", "操作员可能把演示数据当生产事实。", "evidence/api/api_probe_summary.json", "backend/app/api/can.py:13-31,178-212; backend/app/api/eol.py:18-133", "字段级 source/quality/mock 元数据；生产模式禁止无标识 fallback。", "M", True),
    issue("API-003", "P2", "API", "错误处理", "错误响应结构和 trace_id 不统一", "HTTPException 使用 detail，通用 handler 使用平铺结构且 trace_id 可空。", "前端无法稳定展示原因，审计链路断裂。", "evidence/api/security_probe.json", "backend/app/main.py:15-18; backend/app/api/config.py:472-475", "统一异常基类、中间件生成 trace_id、结构化错误和日志关联。", "M"),
    issue("API-004", "P2", "API/CAN", "协议配置", "接口允许 TCP 但运行时不存在 TCP gateway", "保存 TCP 后仍由 UdpCanGateway 运行。", "配置与实际行为不一致。", "evidence/api/get__config.json", "backend/app/api/config.py:319-344; backend/app/can_gateway/manager.py:13", "实现 TcpCanGateway 或拒绝 TCP 并明确未支持。", "M"),
    issue("API-005", "P2", "API/权限", "报告删除", "前端 DELETE 不发送 x-role，后端又把不存在 ID 回退为 Mock 报告", "正常 UI 删除恒 403；伪造 admin 对不存在 ID 返回成功。", "用户流程不可用且接口语义危险。", "evidence/api/security_probe.json", "desktop/src/api/http.ts:21-25; backend/app/api/reports.py:125-126,261-273", "依赖认证上下文；不存在返回 404；前端不自行声明角色。", "M"),
    issue("UI-001", "P2", "UI", "响应式", "1366×768 多页裁切或需页面滚动", "overview/network/curve/manual/auto/alarm 裁切，report/history/settings 使用页面内部滚动。", "兼容分辨率下关键按钮和状态不可见。", "evidence/screenshots/current/ui_runtime_metrics.json", "desktop/src/pages/*.vue; desktop/src/components/layout/AppShell.vue:22", "建立 1366 专用压缩网格，页级 overflow hidden，仅表格内部滚动。", "L"),
    issue("UI-002", "P2", "UI", "顶部状态", "页面主体收到实时数据时顶部 CAN1/CAN2 仍可显示 offline", "新开页截图中状态栏与 CAN 表/仿真状态不一致。", "操作员无法判断真实链路。", "evidence/screenshots/current/03_can_monitor_1920x1080.png", "desktop/src/stores/appStatus.ts:18-58; desktop/src/components/layout/TopStatusBar.vue:41-47", "以单一 channel store 为真源，先加载状态并定义 loading，不用 fallback offline 覆盖。", "M", True),
    issue("UI-003", "P2", "UI", "实时曲线", "显示 0/256 已选择但六图仍有所有曲线", "checkbox 与 series 没有真实绑定。", "用户无法控制监控负载和曲线内容。", "evidence/screenshots/current/05_realtime_curve_1920x1080.png", "desktop/src/pages/RealtimeCurvePage.vue", "按 selected signal 过滤 series，保存选择并增加交互测试。", "M"),
    issue("UI-004", "P2", "UI", "手动控制", "存在 4 个白底原生输入控件", "运行时 computed style 审计检出。", "破坏工业主题并降低暗环境可读性。", "evidence/screenshots/current/ui_runtime_metrics.json", "desktop/src/pages/ManualControlPage.vue", "统一 IndustrialInput/Range 控件和 focus/disabled 样式。", "S"),
    issue("PERF-002", "P2", "前端", "WebSocket 生命周期", "WsClient 无 close/error/reconnect/off，页面 handler 不注销", "路由切换会累积 callbacks；connect 可重复创建 socket。", "长时间页面切换后重复请求和内存增长。", "evidence/commands/search_websocket.txt", "desktop/src/api/websocket.ts:1-15; desktop/src/pages/AutoTestPage.vue:333-343", "实现单例连接状态机、指数退避、unsubscribe/off 和组件 scope cleanup。", "M"),
    issue("DB-003", "P2", "日志", "解码信号", "SignalLogWriter.write 是空函数", "无解析后信号 CSV/Parquet 落盘。", "历史曲线和追溯数据缺失。", "evidence/tests/database_audit.json", "backend/app/storage/signal_log_writer.py:1-3", "实现批量信号日志和质量/会话字段。", "M", False, True),
    issue("DB-004", "P2", "数据库", "事务", "每条 execute 立即 commit，无会话事务/回滚；shutdown 未 close 数据库", "步骤、断言和报告无法原子保存。", "部分失败可留下不一致记录并泄漏句柄。", "evidence/tests/database_audit.json", "backend/app/storage/database.py:8-31; backend/app/services/lifecycle.py:48-52", "增加 transaction context、FK 检查、busy retry 和 shutdown close。", "M"),
    issue("TEST-001", "P2", "测试", "仿真器", "从项目根执行 pytest simulator/tests 收集失败", "ModuleNotFoundError: can_frame_simulator；切入 simulator 目录后 1 条通过。", "README 推荐命令不可复现。", "evidence/tests/simulator_pytest.txt", "simulator/tests/test_profiles.py; simulator/pyproject.toml", "安装 simulator 包或配置 pythonpath，CI 从根执行。", "S"),
    issue("TEST-002", "P2", "测试", "前端/覆盖率", "无 npm test、lint，后端未安装 pytest-cov", "只能证明类型检查和构建，无法证明交互。", "回归风险高，关键 UI 与 WebSocket 无自动测试。", "evidence/tests/frontend_test_attempt.txt; evidence/tests/frontend_lint_attempt.txt; evidence/tests/backend_coverage_attempt.txt", "desktop/package.json; backend/pyproject.toml", "添加 Vitest、ESLint、Playwright/Electron E2E 和覆盖率门槛。", "M"),
    issue("DEPLOY-002", "P2", "依赖", "npm", "npm audit 报 2 high + 2 moderate", "Electron 31、Vite/esbuild/ECharts 依赖链有已知问题。", "扩大桌面端攻击面。", "evidence/tests/npm_audit.json", "desktop/package.json", "升级受支持 Electron/Vite/ECharts，验证兼容并纳入依赖扫描。", "M"),
    issue("REPORT-002", "P2", "报告/UI", "预览", "预览面板不读取真实 DOCX/PDF", "任意行均显示固定 12 页模板元数据。", "无法核对生成文件，JSON/CSV tab 也不是真实内容。", "evidence/screenshots/current/09_report_management_1920x1080.png", "backend/app/api/reports.py:125-145; desktop/src/pages/ReportManagementPage.vue", "提供安全的 PDF 渲染/文本摘要 endpoint，并按真实文件类型预览。", "M"),

    issue("UI-005", "P3", "UI", "视觉还原", "10 页像素差异仍为 28.7%~40.0% 像素超过阈值 10", "报告、一键检测和总览的比例/密度偏差最明显。", "影响视觉一致性但不直接改变业务。", "evidence/screenshots/diff/visual_diff_metrics.csv", "desktop/src/pages/*.vue", "按参考图逐页校准网格、字号、卡片高度和图表比例。", "L"),
    issue("UI-006", "P3", "UI", "ECharts", "控制台出现 2 条容器宽高为 0 的初始化警告", "图表在首次布局时初始化早于容器尺寸。", "偶发空图或首次 resize 闪烁。", "evidence/screenshots/current/browser_console_warnings.json", "desktop/src/components/charts/*.vue", "使用 ResizeObserver 和非零尺寸后 init。", "S"),
    issue("PERF-003", "P3", "性能", "前端包", "主 JS 1,394.53kB，Vite 报 >500kB", "11 页全部同步导入且 ECharts 未拆包。", "首屏和升级包体积偏大。", "evidence/tests/frontend_build.txt", "desktop/src/router/index.ts; desktop/vite.config.ts", "路由懒加载并拆分 ECharts/vendor。", "S"),
    issue("TEST-003", "P3", "测试", "根脚本", "根 npm test 依赖系统 PATH pytest，当前环境失败", "新环境无法一键测试。", "影响审计/CI 可复现性。", "evidence/tests/root_npm_test.txt", "package.json", "显式调用 backend/.venv 或统一 uv run。", "S"),
    issue("DEPLOY-003", "P3", "部署", "运维", "Linux、离线安装、自启动、崩溃恢复、升级回滚未验证", "当前只有 Windows 开发运行证据。", "部署风险未知。", "evidence/commands/os_version.txt", "docs/17_deployment_plan.md; desktop/package.json", "建立 Windows 工控机安装/升级演练和 Linux 后端 CI。", "L"),
    issue("API-006", "P3", "API", "OpenAPI", "大量接口没有明确 response model，路径参数命名与规范不一致", "OpenAPI 112 路由可枚举，但契约约束弱。", "客户端类型和错误契约易漂移。", "evidence/api/api_spec_comparison.json", "backend/app/api/*.py", "为公共 API 添加 request/response Pydantic 模型并做契约测试。", "M"),
]


severity_counts = Counter(item["severity"] for item in issues)
assert severity_counts == Counter({"P0": 5, "P1": 12, "P2": 19, "P3": 6})


ui_average = round(sum(page["score"] for page in visual_pages) / len(visual_pages), 1)


write(
    "AUDIT_INDEX.md",
    f"""
# 工程审计索引

- 审计时间：{AUDIT_TIME}
- 项目：低速无人车线控底盘生产下线管理平台 v{PROJECT_VERSION}
- 审计性质：证据优先的代码、运行、视觉、仿真、安全和部署审计
- 生产就绪结论：**NOT_READY**

## 入口

1. [执行摘要](00_EXECUTIVE_SUMMARY.md)
2. [项目基线](01_PROJECT_BASELINE.md)
3. [UI 还原审计](02_UI_FIDELITY_AUDIT.md)
4. [页面功能审计](03_PAGE_FUNCTION_AUDIT.md)
5. [前端架构审计](04_FRONTEND_ARCHITECTURE_AUDIT.md)
6. [后端 API 审计](05_BACKEND_API_AUDIT.md)
7. [CAN/DBC/协议审计](06_CAN_DBC_PROTOCOL_AUDIT.md)
8. [仿真端到端审计](07_SIMULATION_E2E_AUDIT.md)
9. [EOL 引擎审计](08_EOL_TEST_ENGINE_AUDIT.md)
10. [数据库/日志/报告审计](09_DATABASE_LOG_REPORT_AUDIT.md)
11. [安全审计](10_SECURITY_SAFETY_AUDIT.md)
12. [测试质量审计](11_TEST_QUALITY_AUDIT.md)
13. [性能可靠性审计](12_PERFORMANCE_RELIABILITY_AUDIT.md)
14. [打包部署审计](13_PACKAGING_DEPLOYMENT_AUDIT.md)
15. [问题登记](14_ISSUE_REGISTER.md)
16. [整改计划](15_REMEDIATION_PLAN.md)
17. [审计清单](AUDIT_MANIFEST.md)
18. [机器可读结果](audit_results.json)
19. [CSV 问题单](issue_register.csv)

## 判定口径

`REAL` 仅用于实际运行并取得预期业务结果；`PARTIAL` 表示存在真实链路但语义/闭环不完整；`MOCK` 为固定或 fallback 数据；`STUB` 仅返回预留响应；`MISSING` 为缺失；`UNVERIFIED` 为环境无法验证。构建通过、HTTP 200、按钮有 toast 均不单独等于真实实现。
""",
)


top_ten = [
    "EOL 暂停、中止、急停不终止任务，最终可被覆盖为 PASS。",
    "CAN 全断开时 EOL 仍执行 12 步并 PASS。",
    "高负载积压帧使仿真器停机 5 秒后 CAN2 仍被判在线并允许控制。",
    "无认证且后端默认 admin；维护和删除权限可由请求字段/头伪造。",
    "急停不下发零速/制动帧，安全停车也只有一次发送。",
    "steering_no_response 与 brake_fail 两种故障 profile 错误 PASS。",
    "约 1045fps 输入下只处理约 345.9fps，WebSocket 每帧广播 7 类消息。",
    "核心会话、步骤、断言、帧、信号、告警和报告表均无业务记录。",
    "生成报告中文乱码/方块，PDF 内容不足且缺 DBC/config/software 元数据。",
    "Electron 无生产 dist 入口、后端拉起、安装包和 Python runtime 打包。",
]
write(
    "00_EXECUTIVE_SUMMARY.md",
    f"""
# 执行摘要

## 总结

项目可在 Windows 开发环境启动 FastAPI、Vite 和 Electron；DBC 可真实加载，UDP 仿真报文可进入后端，0x121 在专用 loopback 配置下可真实到达仿真器。然而 EOL、安全联锁、持久化、报告和生产打包存在阻断性缺陷，**不建议连接真实车辆，也不建议上真实台架**。在修复 P0 前仅允许静态审查或隔离 Mock 环境。

{md_table(["指标", "结果", "证据/口径"], [
    ["项目启动", "开发模式可启动", "evidence/commands/backend_startup.txt；evidence/commands/electron_runtime_probe.json"],
    ["仿真运行", "可收帧；默认双向配置不匹配", "evidence/simulation/normal_pass_startup.txt；SIM-001"],
    ["11 页 UI 平均还原度", f"{ui_average}%", "22 张双分辨率截图；10 页像素 diff；系统设置按文档"],
    ["功能总体完成度", f"{functional_completion}%", "REAL=1, PARTIAL=.5, MOCK=.25, STUB=.1 的 148 项加权"],
    ["真实功能实现率", f"{real_completion}% ({all_function_counts['REAL']}/{function_total})", "仅 REAL 计入"],
    ["Mock/Stub 比例", f"{round((all_function_counts['MOCK']+all_function_counts['STUB'])/function_total*100,1)}%", f"MOCK {all_function_counts['MOCK']} + STUB {all_function_counts['STUB']}"],
    ["核心规范 API 路由覆盖", "100% (31/31)", "真实语义实现估计 8/31=25.8%；路由存在不等于完成"],
    ["测试", "后端 30/30；仿真器 1/1（正确 cwd）", "根目录仿真测试收集失败；无前端 test/lint/coverage"],
    ["normal_pass", "实际 PASS，与预期一致", "evidence/simulation/normal_pass_eol_result.json"],
    ["故障仿真", "2/4 故障正确 FAIL；2/4 错误 PASS", "steering_no_response、brake_fail 错误 PASS"],
    ["报告", "文件生成但不可交付", "DOCX 乱码、PDF 中文方块、元数据缺失"],
    ["安全红线", "不满足", "P0 共 5 项"],
    ["问题数量", "P0=5 / P1=12 / P2=19 / P3=6", "共 42 项"],
    ["总体评分", "48/100", "UI 87、功能 46、真实实现 15.5、API 100、测试55、安全28、仿真40、部署20 加权"],
    ["生产就绪", "NOT_READY", "不能用于真实硬件"],
])}

## 最关键的 10 个问题

""" + "\n".join(f"{index}. {text}" for index, text in enumerate(top_ten, 1)) + """

## 建议

下一阶段先冻结 UI 扩展，完成 P0 状态机/断链/急停/认证修复；随后完成真实断言、持久化、报告、吞吐和部署。P0 全部通过故障注入测试前，不允许连接真实车辆。
""",
)


write(
    "01_PROJECT_BASELINE.md",
    f"""
# 项目基线

## 环境

{md_table(["项目", "值", "证据"], [
    ["审计时间", AUDIT_TIME, "evidence/commands/audit_time.txt"],
    ["操作系统", "Windows 10 Pro 10.0.19045 x64", "evidence/commands/os_version.txt"],
    ["Python（backend venv）", "3.14.3", "evidence/commands/backend_python_version.txt"],
    ["uv", "0.10.7", "evidence/commands/uv_version.txt"],
    ["conda", "不可用", "evidence/commands/conda_version.txt"],
    ["Node", "v22.22.2", "evidence/commands/node_version.txt"],
    ["npm", "10.9.7", "evidence/commands/npm_version.txt"],
    ["Electron", "31.7.7", "evidence/commands/electron_version.txt"],
    ["前端", "Vue 3.5.39 / Pinia 2.3.1 / Router 4.6.4 / ECharts 5.6.0 / Vite 5.4.21 / TS 5.9.3", "evidence/commands/npm_list.txt"],
    ["后端", "FastAPI + asyncio + Pydantic + SQLite + cantools", "backend/pyproject.toml；evidence/commands/pip_freeze.txt"],
])}

## 目录与组件

- `desktop/`：Vue 3 renderer、Pinia、Hash Router、ECharts、Electron `main.cjs/preload.cjs`。
- `backend/app/`：FastAPI、UDP gateway、DBC、控制、EOL、报告、存储和 WebSocket。
- `simulator/`：Python profile 驱动 CAN frame simulator。
- `configs/`：station/channels/thresholds/DBC override/test plan/report/storage/theme。
- `assets/Yunle_CAN_integrated_candb_jd.dbc`：实际加载 39 messages、170 signals，SHA 前缀 `387ae48bd84852c8`。
- 完整文件树：[project_file_inventory.txt](evidence/commands/project_file_inventory.txt)。

## Git

当前目录及父级不是 Git 工作树，无法取得 commit hash；`git status` 和 `git log -1` 的失败输出已保存：[git_status.txt](evidence/commands/git_status.txt)、[git_log_last.txt](evidence/commands/git_log_last.txt)。因此审计无法绑定不可变提交，这是可复现性限制。

## 可用命令

- 后端：`backend/.venv/Scripts/python.exe scripts/dev_backend.py`
- 仿真：`backend/.venv/Scripts/python.exe scripts/dev_simulator.py --profile normal_pass`
- Web：`cd desktop && npm.cmd run dev:web`
- Electron：`desktop/node_modules/electron/dist/electron.exe .`（依赖已运行 Vite）
- 后端测试：`cd backend && .venv/Scripts/python.exe -m pytest tests -q`
- 仿真测试：`cd simulator && ../backend/.venv/Scripts/python.exe -m pytest tests -q`
- 前端：`npm.cmd run typecheck`、`npm.cmd run build`

## 静态标记数量

{md_table(["关键词", "数量", "证据"], [[row[0], row[1], f"evidence/commands/search_{row[0].lower().replace('-','_')}.txt"] for row in [
    ("TODO",0),("FIXME",0),("stub",98),("mock",201),("fallback",155),("NotImplemented",0),("setInterval",11),("WebSocket",44),("any",112),("ts-ignore",0),("eslint-disable",0),("console.log",0),("localhost",0),("127_0_0_1",19),("192_168_1",26)
]])}

搜索排除了 `node_modules`、`dist` 和审计输出。完整计数见 [static_search_counts.txt](evidence/commands/static_search_counts.txt)。`mock/stub/fallback` 数量包含类型、文案和实现引用，不直接等于功能项数量。
""",
)


visual_summary_rows = []
for page in visual_pages:
    level = "高度还原" if page["score"] >= 95 else "基本还原" if page["score"] >= 85 else "部分还原" if page["score"] >= 70 else "低还原度"
    visual_summary_rows.append([page["route"], page["name"], page["score"], level, page["priority"]])

visual_sections = []
for page in visual_pages:
    ref = f"evidence/screenshots/reference/{page['id']}_{page['route'].strip('/').replace('-', '_')}.png" if page["id"] != "11" else "无独立参考；docs/ui/pages/11_system_settings.md"
    current_base = {
        "01": "overview", "02": "network_config", "03": "can_monitor", "04": "signal_dashboard", "05": "realtime_curve",
        "06": "manual_control", "07": "auto_test", "08": "alarm_diagnosis", "09": "report_management", "10": "history", "11": "system_settings",
    }[page["id"]]
    diff = f"evidence/screenshots/diff/{page['id']}_{current_base}_reference_current_diff.png" if page["id"] != "11" else "不适用"
    reference_line = f"- 参考：[{ref}]({ref})" if page["id"] != "11" else "- 参考：无独立参考图；按 `docs/ui/pages/11_system_settings.md` 与统一设计语言审计"
    diff_line = f"- 差异图：[{diff}]({diff})" if page["id"] != "11" else "- 差异图：不适用"
    categories = ["布局/30", "组件/20", "内容/15", "样式/15", "细节/10", "1920/5", "1366/5"]
    visual_sections.append(
        f"""
## {page['id']}. {page['name']} `{page['route']}` — {page['score']}/100

- 当前 1920：[截图](evidence/screenshots/current/{page['id']}_{current_base}_1920x1080.png)
- 当前 1366：[截图](evidence/screenshots/current/{page['id']}_{current_base}_1366x768.png)
{reference_line}
{diff_line}
- 分项：{', '.join(f'{label}={value}' for label, value in zip(categories, page['parts']))}
- 像素证据：{f"MAD={page['mad']}; |diff|>10 的像素={page['changed']}%" if page['mad'] is not None else '无独立参考，不做像素差分'}。
- 差异：{page['gaps']}
- 缺失：{page['missing']}
- 多余/新增：{page['extra']}
- 1920×1080：{page['w1920']}
- 1366×768：{page['w1366']}
- 建议：优先修复功能真实性与 1366 裁切，再按 diff 校准尺寸；优先级 {page['priority']}。
"""
    )

write(
    "02_UI_FIDELITY_AUDIT.md",
    f"""
# UI 视觉还原审计

## 方法

实际运行 Vite/Electron renderer，在 1920×1080 与 1366×768 采集 22 张截图；前 10 页将当前 1920 图缩放至参考图 1672×941 后生成绝对差异和三联图。像素差异受窗口标题栏、动态时间和数据变化影响，仅作证据，不直接换算评分。系统设置按需求文档和统一设计语言评分。

{md_table(["路由", "页面", "评分", "等级", "优先级"], visual_summary_rows)}

平均还原度：**{ui_average}/100**。前 10 页像素 MAD 为 18.743~25.333，超过 10 灰度差的像素为 28.680%~39.951%。原始指标：[visual_diff_metrics.csv](evidence/screenshots/diff/visual_diff_metrics.csv)，运行尺寸指标：[ui_runtime_metrics.json](evidence/screenshots/current/ui_runtime_metrics.json)。

## 共享结论

- 1920×1080：11 页 document 均等于 viewport，未见页面级滚动和大红 Failed to fetch；ECharts 均有非零 canvas。
- 1366×768：CAN 监控、信号仪表盘最稳定；其余多页裁切或改为页面内部滚动，未满足“核心内容一屏”。
- Electron：`frame:false`、`Menu.setApplicationMenu(null)`、深色自定义标题栏实际存在，无 Windows 原生菜单/白标题栏。
- 离线：抽查 5 页均显示 Mock/离线状态，无 Failed to fetch 横幅，见 `offline_*` 截图和 [offline_runtime_metrics.json](evidence/screenshots/current/offline_runtime_metrics.json)。
- 控制台：2 条 ECharts 宽高为 0 的警告，见 [browser_console_warnings.json](evidence/screenshots/current/browser_console_warnings.json)。

""" + "\n".join(visual_sections),
)


function_summary = []
function_sections = []
for page in function_pages:
    m = page["metrics"]
    function_summary.append([page["route"], m["total"], m["real"], m["partial"], m["mock"], m["stub"], m["missing"], m["functional_completion"], m["real_completion"]])
    function_sections.append(
        f"""
## {page['name']} `{page['route']}`

{md_table(["功能", "状态", "依据"], [[name, status, basis] for name, status, basis in page['functions']])}

合计：REAL {m['real']}、PARTIAL {m['partial']}、MOCK {m['mock']}、STUB {m['stub']}、MISSING {m['missing']}、UNVERIFIED {m['unverified']}；加权功能完成率 **{m['functional_completion']}%**，真实实现率 **{m['real_completion']}%**。
"""
    )

write(
    "03_PAGE_FUNCTION_AUDIT.md",
    f"""
# 11 页功能实现审计

## 计分口径

- 加权功能完成率：`(REAL + 0.5×PARTIAL + 0.25×MOCK + 0.1×STUB) / 总项数`。
- 真实实现率：`REAL / 总项数`。
- Mock/Stub 不计为真实实现；接口存在但未形成业务闭环为 PARTIAL。

{md_table(["页面", "总项", "REAL", "PARTIAL", "MOCK", "STUB", "缺失", "功能%", "真实%"], function_summary)}

总计 {function_total} 项：REAL {all_function_counts['REAL']}、PARTIAL {all_function_counts['PARTIAL']}、MOCK {all_function_counts['MOCK']}、STUB {all_function_counts['STUB']}、MISSING {all_function_counts['MISSING']}。总体加权功能完成率 **{functional_completion}%**，真实实现率 **{real_completion}%**。

""" + "\n".join(function_sections),
)


write(
    "04_FRONTEND_ARCHITECTURE_AUDIT.md",
    """
# 前端架构审计

## 已验证优点

- Vue 3 Composition API、Pinia、Vue Router、TypeScript 能通过 `vue-tsc --noEmit`。
- 11 页共享 `AppShell/SidebarNav/TopStatusBar/WindowChrome`，深色 token 统一。
- ECharts 公共组件在 `onBeforeUnmount` 调用 `dispose` 并移除 window resize。
- 页面轮询 timer 多数在卸载时清理；离线 fallback 不出现大红横幅。
- Electron preload 开启 `contextIsolation:true`、`nodeIntegration:false`，仅暴露三项窗口控制 IPC。

## 关键问题

| 项目 | 结论 | 代码/证据 |
| --- | --- | --- |
| API 封装 | `apiGet` 丢弃错误 body；DELETE 无 headers/body 能力 | `desktop/src/api/http.ts:1-25` |
| WebSocket | 无 close/error/reconnect/off；所有页面订阅 `*`；handler 永不删除 | `desktop/src/api/websocket.ts:1-15` |
| 重复连接 | AppShell、页面和 store 都可能调用 connect | `stores/appStatus.ts:61-72`; `pages/*` |
| 请求放大 | `signals.timeseries.batch` 每条消息触发 HTTP GET | `stores/signals.ts:75-80` |
| CAN 重复 upsert | 同时消费 raw_frame 与 latest_frame_update | `stores/can.ts:130-136` |
| 曲线选择 | UI checkbox 与 series 不一致 | `RealtimeCurvePage.vue`; 运行截图 |
| 响应式 | AppShell `.content{overflow:auto}`；多页固定网格在 1366 裁切 | `AppShell.vue:22`; runtime metrics |
| 图表 resize | 只监听 window resize，无 ResizeObserver；首次 0 尺寸警告 | chart components; console evidence |
| 类型质量 | 搜索到 `any` 112 处；无 ts-ignore | `evidence/commands/search_bany_b.txt` |
| Mock 比例 | fallback 155、mock 201 处；真实/Mock 来源缺统一类型 | 搜索证据 |
| 错误边界 | 无全局 Vue error boundary；toast 解析方式各页不同 | pages/stores |
| preload | IPC 白名单较小是优点；未设置 Chromium sandbox/CSP | `electron/main.cjs`; `index.html` |
| Node API | renderer 未直接调用 Node API | 静态搜索通过 |
| 前端直发 CAN | 未发现；控制均走 HTTP 后端 | ManualControlPage/store |

## 生命周期结论

ECharts dispose 基本正确，但 WebSocket handler 和连接生命周期不正确。路由来回切换报告、历史、EOL、告警页面会持续注册 handler；长期运行风险为重复请求、重复 toast 和内存增长。建议将 WebSocket 订阅返回 unsubscribe，并由组件 scope 清理；图表改用 ResizeObserver。

## 硬编码和异常状态

页面具备完整 fallback 外观，但许多 API 本身也返回固定数据，导致 `backendOnline=true` 时仍显示 Mock 内容。应在 API 类型中加入 `data_source`, `mock`, `quality`, `updated_at`，生产模式禁止无标识 fallback。
""",
)


write(
    "05_BACKEND_API_AUDIT.md",
    """
# FastAPI 与接口审计

## 自动枚举与覆盖

- OpenAPI：112 个 HTTP operation，完整清单 [openapi_routes.csv](evidence/api/openapi_routes.csv)。
- 资料包核心规范：31 个 operation；路径归一化后 31/31 有对应路由，路由覆盖率 100%。
- 路径参数名有 10 处 `{id}` 对 `{sid}/{rid}` 差异，不影响路由但影响契约一致性。
- 选择 56 个页面/按钮接口实测，均返回 HTTP 200；其中至少 16 个明确 `stub:true`。
- 核心 31 接口按语义保守分类：REAL 8、PARTIAL 13、STUB 4、MOCK 6、MISSING 0；真实实现率约 **25.8%**。这不是 OpenAPI 路由覆盖率。

证据：[API probe summary](evidence/api/api_probe_summary.json)、[API spec comparison](evidence/api/api_spec_comparison.json)、每个响应在 `evidence/api/*.json`。

## 主要接口组

| 组 | 路由状态 | 真实状态 |
| --- | --- | --- |
| health/DBC | 存在 | DBC status/reload 真实，39 messages/170 signals |
| CAN channel | 存在 | UDP start/stop/receive 真实；TCP 不存在；self-test Stub |
| CAN monitor | 存在 | latest 聚合真实；decode details/statistics/export 多为 Mock/Stub |
| signals | 存在 | current 部分真实；dashboard/timeseries 混合 fallback；保存/导出 Stub |
| control | 存在 | 0x121 send/scheduler 真实；状态展示和安全停车不完整 |
| EOL | 存在 | 内存演示状态机；暂停/中止/急停语义失败 |
| alarms | 存在 | 当前告警部分真实；历史/建议/导出/放行多为 Mock/Stub |
| reports/history | 存在 | 扫描少量真实，列表/预览/下载/趋势多为 Mock/Stub |
| config/system | 存在 | DBC、原子配置、历史部分真实；导入/导出 Stub，权限不可信 |

## 契约与异常

- Pydantic 在系统配置、维护和 0x121 命令等部分路径使用；许多 dashboard 直接返回 dict，无 response model。
- 全局 500 handler 返回平铺 `{code,message,details,trace_id}`，FastAPI HTTPException 则返回 `{detail:...}`；trace_id 多为空。
- `apiGet` 对非 2xx 只保留 status text，前端拿不到结构化原因。
- CORS 接受任意 Origin 且 credentials=true；安全探测中恶意 Origin 被回显。
- 无 OpenAPI security scheme、认证中间件和可信用户上下文。
- 部分 config/report 操作写 operator_actions/config_history，但控制、EOL 和导出链路不完整。
- 文件删除虽限制 `REPORTS_DIR`，但角色仅由 header 声明；不存在 ID 被 `_find_report` 回退为 Mock，错误返回成功。

## WebSocket

3 秒观察实际收到 5,292 条消息：`can.raw_frame`, `can.latest_frame_update`, `can.decoded_frame`, `can.statistics`, `signals.current`, `signals.dashboard`, `signals.timeseries.batch` 各 744 条，`alarms.current` 84 条。文档要求 statistics 1Hz、signals 约 10Hz，当前实现严重超发。WebSocket 无发送队列、节流、背压、客户端慢消费隔离。
""",
)


write(
    "06_CAN_DBC_PROTOCOL_AUDIT.md",
    """
# CAN、DBC 与 USR-CAN115 协议审计

## DBC

- `assets/*.dbc` 自动扫描：已验证。
- 实际加载：`Yunle_CAN_integrated_candb_jd.dbc`，SHA 前缀 `387ae48bd84852c8`，39 messages、170 signals。
- cantools 加载成功；无文件/解析失败路径会进入 raw-only。
- 0x101 枚举实测：0 idle、1 charging、2 discharging、3 reserved。
- 0x102 输入 `0x8001` 解为无符号 bitmap 32769；但 individual bool 未在 known decoder 中展开。
- override 配置明确 0x121 int8、0x102 unsigned、0x104~0x109 可变 cell、Torque 为相电流 A。

## 13 字节协议

实测 packet：`08 00 00 01 21 40 C4 3C 14 02 00 00 00`。

| 检查 | 结果 |
| --- | --- |
| 长度 13 | 通过 |
| Byte0 FF/RTR/保留位/DLC | 编解码存在 |
| Byte1~4 CAN ID 大端 | 0x00000121，正确 |
| Byte5~12 固定 8 byte | 正确 |
| DLC > 8 | 标记 `dlc_error` |
| 保留位非 0 | 标记 `reserved_bits_error` |
| 粘包两帧 + 5 字节余量 | 解出 0x121/0x77，余 5 |
| UDP 半包跨 datagram | **失败**：拼成伪 0x121 且 parse_status=ok，无重同步 |

完整结果：[protocol_probe.json](evidence/tests/protocol_probe.json)。

## 0x121

| 输入 | 补码 | payload 中转角字节 |
| --- | --- | --- |
| -120 | 0x88 | 88 |
| -60 | 0xC4 | C4 |
| 0 | 0x00 | 00 |
| 60 | 0x3C | 3C |
| 120 | 0x78 | 78 |

单元测试和 loopback 实发均通过；超速与急停时 send-once 返回 409。但 UI 的 `bytes_hex` 展示与 authoritative `data`/实发 payload 不一致，见 SAFE-006。

## 通道、统计和缓存

- CAN1/CAN2 独立 UDP socket 和统计对象；控制通道配置默认为 CAN2。
- `recent_frames` 为两通道共享 2,000 帧，低于文档建议；SignalStore 每信号 3,000 点。
- fps 为启动以来累计平均，不是滚动实时帧率。
- `asyncio.create_task(on_frame)` 无界，导致处理积压和在线时效错误。
- 0x123/0x126/NMT 默认关闭；非维护模式 gate 和 0x126 126..525 范围测试通过。没有发现默认发送这些报文。

## 结论

基础 13-byte codec 与 0x121 补码是当前较可靠部分；UDP 边界处理、0x102 信号化、实时统计和高负载背压尚不满足车辆控制要求。
""",
)


sim_rows = [
    ["normal_pass", "PASS", "PASS", "一致", "12", "已生成", "否"],
    ["bms_low_soc", "FAIL", "FAIL", "结果一致但错误地在第1步失败", "1", "已生成", "未触发/未证明"],
    ["warning_fault", "FAIL", "FAIL", "结果一致但错误地在第1步失败", "1", "已生成", "未触发/未证明"],
    ["steering_no_response", "FAIL", "PASS", "不一致", "12", "生成错误 PASS", "否"],
    ["brake_fail", "FAIL", "PASS", "不一致", "12", "生成错误 PASS", "否"],
]
write(
    "07_SIMULATION_E2E_AUDIT.md",
    f"""
# 仿真与端到端审计

## 运行链路

实际启动 FastAPI、Python simulator、Vite renderer，并用 loopback 配置补做 0x121 双向控制。后端监听 127.0.0.1:8234/8235，仿真器设备端为 127.0.0.1:12341/12342。默认生产配置的发送端仍是 [REDACTED_CAN1_GATEWAY]/99:1234，因此标准开发命令并非完整双向闭环。

normal profile 收到/展示主要 ID 包括 0x51、0x77、0x100~0x105、0x121、0x168、0xE1、0x703、0x704；DBC status loaded，SignalStore 和 WebSocket 有更新。证据：[latest frames](evidence/simulation/normal_pass_latest_frames.json)、[signals](evidence/simulation/normal_pass_signals.json)、[channels](evidence/simulation/normal_pass_channels.json)。

{md_table(["Profile", "预期", "实际", "判定", "执行步数", "报告", "安全停车"], sim_rows)}

## 控制闭环

专用 loopback 配置下，仿真器实际收到 10 个 0x121 帧，覆盖 send-once、periodic 和 safe-stop；-60/60 编码为 C4/3C，超速和急停阻断返回 409。见 [control_loopback_e2e.json](evidence/simulation/control_loopback_e2e.json) 与 [simulator RX](evidence/simulation/control_loopback_simulator_rx.txt)。该证据不代表默认生产配置可安全使用。

## 降级与停止

- 后端停止：抽查 5 页完整 fallback，无大红横幅，见 offline 截图。
- simulator 停止：低负载最终会离线；高负载下因处理积压，5 秒后 CAN2 仍在线并允许控制。
- WebSocket：实际推送存在，但频率远超规范。

## 结论

仿真报文能够真正进入后端和页面，不是仅进程启动；但故障 profile 判定只有 2/4 符合预期，安全停车没有由 EOL 故障自动触发，默认双向端口配置不一致。仿真评分 40/100。
""",
)


write(
    "08_EOL_TEST_ENGINE_AUDIT.md",
    """
# 一键检测引擎审计

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
""",
)


write(
    "09_DATABASE_LOG_REPORT_AUDIT.md",
    """
# 数据库、日志与报告审计

## SQLite

- 11 个要求表全部存在，`integrity_check=ok`，journal_mode=WAL，主要 session/frame/signal/step 索引存在。
- 审计独立连接显示 foreign_keys=false；生产 Database 初始化脚本执行 `PRAGMA foreign_keys=ON`，但该设置只对单连接有效。
- 业务行数：test_sessions/test_steps/test_assertions/raw_can_frames/decoded_signals/signal_statistics/alarms/reports/software_versions 全部 0。
- operator_actions=206，config_history=53，说明仅配置/部分操作审计实际落库。
- Database 每次 `execute` 立即 commit，无事务 context；shutdown 没有 close。

完整 schema、列、索引与行数：[database_audit.json](evidence/tests/database_audit.json)。

## 日志

- RawLogWriter 每帧同步 open/append/close `data/logs/raw_can_current.csv`。
- 审计时该单文件约 119.08MB；无轮转、压缩、会话切分和最大空间控制。
- SignalLogWriter 是 no-op；解码信号未落 CSV/Parquet。
- 应用日志存在，但 trace_id 不统一；高频 backend runtime log 达数 MB。

## 报告

实际生成 15 JSON、15 DOCX、15 PDF；未生成 CSV。抽检 normal PASS 和 low-SOC FAIL：

| 检查 | PASS 报告 | FAIL 报告 |
| --- | --- | --- |
| JSON 可打开 | 是 | 是 |
| DOCX 可打开 | 是，但中文乱码 | 是，但中文乱码 |
| PDF 可打开 | 是，1页/1526B | 是，1页/1524B |
| PDF 中文 | 方块/不可读 | 方块/不可读 |
| software_version | 缺失 | 缺失 |
| dbc_hash | 缺失 | 缺失 |
| config version/hash | 缺失 | 缺失 |
| operator | 有 | 有 |

证据：[report_validation.json](evidence/tests/report_validation.json)、[PASS 渲染](evidence/screenshots/current/generated_normal_pass_report_page1.png)、[FAIL 渲染](evidence/screenshots/current/generated_bms_low_soc_report_page1.png)。

报告 API 的预览是固定模板；打印、导出、重新生成、打开目录为 Stub；报告表没有记录，目录扫描结果不能可靠关联会话。
""",
)


safety_rows = [
    ["UI 直接发 CAN", "通过", "未发现 renderer socket/Node API，均走后端 HTTP"],
    ["控制经后端", "通过", "ManualControl store 调用 /control"],
    ["所有控制经 SafetyInterlock", "部分", "send/start/safe-stop 调用；EOL 不调用；急停另行处理"],
    ["控制通道唯一", "部分", "配置 gate 存在，默认 CAN2；无认证"],
    ["急停优先级", "失败", "不发送停车帧；EOL 不停止"],
    ["安全停车", "失败", "单次发送，无反馈确认"],
    ["关键报文在线", "失败", "用处理时间，积压可伪在线"],
    ["严重告警", "部分", "手动发送 interlock 检查；EOL/展示不一致"],
    ["速度/转角限制", "通过（编码 API）", "超速阻断、转角 clamp 测试通过"],
    ["看门狗", "失败", "UI 固定 OK(120ms)，无 watchdog service"],
    ["数据库不可写", "部分", "启动时检查一次；EOL 运行中不检查"],
    ["DBC 未加载", "部分", "可配置 raw control；EOL 不检查"],
    ["0x123/0x126/NMT 默认关", "通过默认值", "gate 单测通过"],
    ["维护模式管理员确认", "失败可信身份", "确认文本存在，但请求可自称 admin"],
    ["人工放行", "Stub", "无审批流"],
    ["报告删除", "失败", "x-role 可伪造；前端又无法正常发送"],
    ["配置导入", "Stub", "未解析文件"],
    ["路径穿越", "部分", "删除有父目录检查；其余文件操作多为 Stub"],
    ["Electron isolation", "基本通过", "contextIsolation true、nodeIntegration false；无 sandbox/CSP"],
    ["CORS", "失败", "任意 Origin + credentials"],
    ["认证授权", "失败", "无 auth scheme，默认 admin"],
    ["Mock 标识", "失败", "部分固定 API 不标 mock，顶部可显示关闭"],
    ["异常保守失败", "失败", "EOL 断链/转向/制动故障可 PASS"],
]
write(
    "10_SECURITY_SAFETY_AUDIT.md",
    f"""
# 安全与安全联锁审计

{md_table(["检查", "结果", "依据"], safety_rows)}

## 动态安全证据

1. 超速与已触发急停时手动 send-once 被 409 阻断。
2. EOL pause/abort/emergency 不停止后台任务。
3. 两通道断开时 EOL 仍 PASS。
4. 约 1000fps 压力后停止 simulator 5 秒，CAN2 仍 online 且控制请求 200。
5. 无认证可进入 maintenance；`x-role:admin` 可使不存在报告删除返回 200。
6. 任意 Origin CORS 预检被允许。

## P0

SAFE-001 至 SAFE-005 均可能造成错误车辆动作、错误放行或无授权控制。安全评分 **28/100**。在这些问题关闭并由独立故障注入测试证明前，禁止连接真实车辆。

## Electron

无原生菜单、无框窗口和 IPC 白名单符合目标；仍需 `sandbox:true`、CSP、导航/新窗口限制以及生产 URL 白名单。renderer 未发现直接 Node/CAN 访问。
""",
)


write(
    "11_TEST_QUALITY_AUDIT.md",
    """
# 测试质量审计

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
""",
)


write(
    "12_PERFORMANCE_RELIABILITY_AUDIT.md",
    """
# 性能与可靠性审计

## 启动与负载

- FastAPI 首次审计启动约 1.3s；DBC 和两个 UDP socket 可初始化。
- Electron 进程在 6s 检查点存活且 4 个进程 responding；未取得可靠首屏 paint timing，因此不写“首屏通过”。
- 60s 目标总 1045fps：实际后端处理增量约 345.9fps；后端工作集 152.62→152.71MB；HTTP 最大 85ms、0 failures；raw log 增长 2.8MB。
- backend CPU 采样为全机归一 5%，不能解释为无压力；吞吐和积压证据显示事件循环处理不过来。

完整数据：[stress summary](evidence/tests/stress_1000fps_60s_summary.json)、[CSV](evidence/tests/stress_1000fps_60s.csv)。

## 可靠性问题

- 每帧 create_task，无界任务数量和时效。
- 每帧同步文件 I/O；每帧 7 次 WebSocket 序列广播。
- statistics payload 包含 recent frames，进一步放大序列化。
- simulator 停止后仍处理积压，在线/周期统计错误。
- WebSocket 无重连/off/backpressure，页面切换累积 handler。
- SQLite 每语句 commit，无事务、无 shutdown close。
- 单文件日志无轮转；长期运行数据增长无界。

## 未执行

未继续 10 分钟 1000fps：60 秒已证明无界 backlog 和磁盘增长，继续会放大主机/磁盘风险而不增加结论强度。未做真实硬件 socket/防火墙/丢包压力。该项明确为未执行，不判通过。

性能可靠性结论：当前适合低速演示数据，不适合资料包目标高帧率长期运行。
""",
)


write(
    "13_PACKAGING_DEPLOYMENT_AUDIT.md",
    """
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
""",
)


issue_rows = [[item[key] for key in ["issue_id", "severity", "category", "module", "title", "blocks_production", "vehicle_safety", "effort", "status"]] for item in issues]
issue_details = []
for item in issues:
    issue_details.append(
        f"""
## {item['issue_id']} [{item['severity']}] {item['title']}

- 分类/模块：{item['category']} / {item['module']}
- 现象：{item['phenomenon']}
- 影响：{item['impact']}
- 复现：{item['reproduction']}
- 证据：`{item['evidence']}`
- 代码：`{item['code']}`
- 原因：{item['cause']}
- 建议：{item['recommendation']}
- 工作量/依赖：{item['effort']} / {item['dependencies']}
- 状态：{item['status']}；阻止生产：{item['blocks_production']}；车辆安全：{item['vehicle_safety']}
"""
    )

write(
    "14_ISSUE_REGISTER.md",
    f"""
# 问题登记

共 42 项：P0={severity_counts['P0']}、P1={severity_counts['P1']}、P2={severity_counts['P2']}、P3={severity_counts['P3']}。

{md_table(["ID", "级别", "分类", "模块", "标题", "阻产", "车辆安全", "工作量", "状态"], issue_rows)}

""" + "\n".join(issue_details),
)


csv_fields = [
    "issue_id", "category", "module", "severity", "title", "phenomenon", "impact", "reproduction", "evidence", "code",
    "cause", "recommendation", "effort", "dependencies", "status", "blocks_production", "vehicle_safety",
]
with (AUDIT / "issue_register.csv").open("w", encoding="utf-8-sig", newline="") as fp:
    writer = csv.DictWriter(fp, fieldnames=csv_fields)
    writer.writeheader()
    writer.writerows(issues)


remediation_rows = [
    ["A-01", "SAFE-001/002/005", "重写 EOL 可取消状态机与急停停车闭环", "engine.py, api/eol.py, control/*", "状态与确认 UI", "task cancel、safe stop、interlock", "故障注入+硬超时", "pause/abort/e-stop 不再执行下一步且车辆反馈为 0", "SafetyInterlock", "L", "高"],
    ["A-02", "SAFE-003/PERF-001", "消除积压导致的伪在线", "udp_gateway.py, lifecycle.py, statistics.py", "显示 source age", "有界队列、节流、receive timestamp", "1000fps+断链", "5s 内离线且控制 409", "队列设计", "L", "高"],
    ["A-03", "SAFE-004", "服务端认证和 RBAC", "main.py, api/*, desktop auth", "登录/锁屏/角色显示", "token/session/RBAC", "越权/API 安全", "伪造 role/header 无效", "部署身份源", "L", "高"],
    ["A-04", "SAFE-006/007/008", "统一预览、实际编码和联锁状态", "api/control.py, control_121.py", "只展示 authoritative bytes", "统一 DTO 和停车状态机", "loopback golden vectors", "UI byte=实发 byte，停车有反馈", "A-02", "M", "高"],
    ["B-01", "EOL-001/002", "按 YAML 实现 12 步真实断言", "eol/*, configs/test_plan.yaml", "实时步骤/断言", "动作、采样窗、阈值、失败策略", "五 profile+断链/DBC/DB", "全部预期一致", "A 阶段", "XL", "高"],
    ["B-02", "DB-001/003/004", "会话 UoW 与全链路持久化", "storage/*, lifecycle.py, eol/*", "历史读取真实 source", "事务、批量写、恢复", "回滚/并发/重启", "核心表完整且可追溯", "schema migration", "L", "中"],
    ["B-03", "REPORT-001/002", "生产报告与真实预览", "reports/*, api/reports.py", "真实 PDF/JSON/CSV preview", "模板/字体/元数据/DB", "渲染 diff、可打开", "PASS/FAIL 报告内容完整", "B-02", "L", "中"],
    ["B-04", "SIM-001", "dev/prod 配置隔离", "configs, scripts/dev_*", "明确 Mock banner", "profile 强制 loopback", "禁止生产 IP 测试", "默认联调不触碰真实网段", "认证配置", "M", "高"],
    ["C-01", "UI-001/005", "逐页 1366 和像素校准", "pages/*.vue, styles", "全部", "无", "双分辨率截图 diff", "1920 一屏；1366 核心可操作", "B 阶段数据契约", "L", "低"],
    ["C-02", "UI-002/003/004/006", "修复状态源、曲线选择、表单和图表初始化", "stores, pages, chart components", "交互和主题", "状态契约", "Playwright", "无矛盾状态/白控件/空图", "API source metadata", "M", "中"],
    ["D-01", "API-002/004", "替换 dashboard/diagnostic Mock 与 TCP 假配置", "api/can.py, signals.py", "来源标记", "真实统计/诊断/TCP或拒绝", "契约/E2E", "生产无无标识 fallback", "B-02", "L", "中"],
    ["D-02", "API-003/005/006", "统一 API 契约与错误", "main.py, api models, http.ts", "统一错误 toast", "response model/trace_id/404", "OpenAPI contract", "错误可追踪且删除安全", "A-03", "M", "中"],
    ["D-03", "历史/报告/导出 Stub", "实现文件导出、下载、回放和审批", "api/history.py, reports.py, signals.py", "真实下载进度", "安全文件服务", "文件/权限 E2E", "按钮无 stub", "B-02/B-03", "L", "中"],
    ["E-01", "API-001/PERF-002", "WebSocket 节流、背压和生命周期", "ws manager, lifecycle, websocket.ts", "取消订阅/重连", "topic cadence/queue", "10min soak", "无重复订阅且频率达标", "A-02", "L", "中"],
    ["E-02", "DB-002/CAN-001/002", "日志轮转与实时统计", "raw_log_writer.py, statistics.py", "真实缓冲/磁盘告警", "批量 IO/滚动 fps", "1000fps 10min", "无 backlog/磁盘失控", "E-01", "M", "中"],
    ["E-03", "DEPLOY-001/002/003/PERF-003", "Windows 安装包和依赖升级", "desktop package/electron, build scripts", "懒加载", "backend packaging/process manager", "干净机安装/升级", "离线启动、崩溃恢复", "A-03", "L", "中"],
    ["F-01", "TEST-001/002/003", "建立 CI 和覆盖率门槛", "tests, package scripts", "Vitest/Playwright", "pytest/coverage", "全套 CI", "根目录一键复现", "前述阶段", "M", "低"],
    ["F-02", "全部 P0/P1", "封闭台架生产验收", "验收脚本/记录", "操作员验收", "硬件故障注入", "24h soak/断电/断链", "独立签字后仅 PILOT_READY", "A-E 全完成", "XL", "高"],
]

write(
    "15_REMEDIATION_PLAN.md",
    f"""
# 分阶段整改计划

{md_table(["任务", "Issue", "目标", "修改文件", "前端", "后端", "测试", "验收", "依赖", "工作量", "风险"], remediation_rows)}

## 阶段门禁

- 阶段 A：P0 安全和车辆控制。完成前禁止真实台架和车辆。
- 阶段 B：P1 生产阻塞和错误结论。完成后才可申请封闭台架。
- 阶段 C：UI 高还原和关键可操作性，不得掩盖真实状态。
- 阶段 D：Mock/Stub 替换为真实服务。
- 阶段 E：性能、可靠性、打包和部署。
- 阶段 F：生产验收；至少 normal/全部故障/断链/断电/DB失败/DBC失败/急停以及 24h soak。

## 时间优先级

- 立即必须修复：全部 P0，EOL-001，PERF-001，API-001。
- 上台架前必须修复：全部 P0/P1，DBC-001，API-003，DB-001/003/004。
- 量产前必须修复：全部 P0/P1/P2、安装包、报告模板、24h 稳定性和权限审计。
- 可延期：纯像素级 P3、进一步 bundle 优化，但不能延期 ECharts 空图和根测试可复现性。
""",
)


audit_results = {
    "audit_time": AUDIT_TIME,
    "project_version": PROJECT_VERSION,
    "overall_score": 48,
    "ui_fidelity_score": ui_average,
    "functional_completion_score": functional_completion,
    "real_implementation_score": real_completion,
    "api_coverage_score": 100.0,
    "test_score": 55,
    "safety_score": 28,
    "simulation_score": 40,
    "deployment_score": 20,
    "production_readiness": "not_ready",
    "score_method": {
        "overall_weights": {"ui": 0.15, "functional": 0.15, "real": 0.20, "api_route_coverage": 0.10, "test": 0.10, "safety": 0.15, "simulation": 0.10, "deployment": 0.05},
        "functional_weights": {"REAL": 1.0, "PARTIAL": 0.5, "MOCK": 0.25, "STUB": 0.1, "MISSING": 0.0, "UNVERIFIED": 0.0},
    },
    "pages": [
        {
            "route": visual["route"],
            "name": visual["name"],
            "ui_score": visual["score"],
            "function_metrics": next(page["metrics"] for page in function_pages if page["route"] == visual["route"]),
            "functions": [dict(name=name, status=status, evidence=basis) for name, status, basis in next(page["functions"] for page in function_pages if page["route"] == visual["route"])],
        }
        for visual in visual_pages
    ],
    "function_totals": {**all_function_counts, "total": function_total},
    "api_results": {"openapi_operations": 112, "core_spec_operations": 31, "core_routes_present": 31, "core_real_estimate": 8, "core_partial_estimate": 13, "core_stub_estimate": 4, "core_mock_estimate": 6},
    "issues": {"p0": severity_counts["P0"], "p1": severity_counts["P1"], "p2": severity_counts["P2"], "p3": severity_counts["P3"]},
    "test_results": {
        "backend": {"passed": 30, "failed": 0, "warnings": 5},
        "simulator_from_root": {"passed": 0, "collection_errors": 1},
        "simulator_from_package_dir": {"passed": 1, "failed": 0},
        "frontend_typecheck": "passed",
        "frontend_build": "passed",
        "frontend_test": "missing_script",
        "frontend_lint": "missing_script",
        "coverage": "unavailable_pytest_cov_not_installed",
    },
    "simulation_results": {
        "normal_pass": {"expected": "PASS", "actual": "PASS", "matched": True},
        "bms_low_soc": {"expected": "FAIL", "actual": "FAIL", "matched": True, "semantic_issue": "failed_at_step_1"},
        "warning_fault": {"expected": "FAIL", "actual": "FAIL", "matched": True, "semantic_issue": "failed_at_step_1"},
        "steering_no_response": {"expected": "FAIL", "actual": "PASS", "matched": False},
        "brake_fail": {"expected": "FAIL", "actual": "PASS", "matched": False},
        "control_loopback": {"frames_received": 10, "int8_vectors": "passed", "overspeed_blocked": True, "emergency_blocked": True},
    },
    "blocking_issues": [item["issue_id"] for item in issues if item["blocks_production"] == "是"],
    "unexecuted": [
        "真实车辆/真实台架：因 P0 安全问题禁止执行",
        "1000fps 10分钟：60秒已出现无界积压与磁盘增长，继续存在主机风险",
        "Linux 和干净机安装：当前只有 Windows 环境且无安装包",
        "真实打印/目录打开/导出：接口为 Stub",
        "覆盖率：pytest-cov 未安装，前端无 test/lint script",
    ],
}
(AUDIT / "audit_results.json").write_text(json.dumps(audit_results, ensure_ascii=False, indent=2), encoding="utf-8")


write(
    "../AUDIT_REPORT.md",
    f"""
# 工程审计报告入口

审计时间：{AUDIT_TIME}  
总体评分：**48/100**  
UI 平均还原度：**{ui_average}/100**  
真实功能实现率：**{real_completion}%**  
生产就绪等级：**NOT_READY**

- [完整审计索引](audit/AUDIT_INDEX.md)
- [执行摘要](audit/00_EXECUTIVE_SUMMARY.md)
- [问题登记](audit/14_ISSUE_REGISTER.md)
- [整改计划](audit/15_REMEDIATION_PLAN.md)
- [机器可读结果](audit/audit_results.json)

核心结论：项目可开发启动和 Mock/UDP 仿真，但 EOL 停止控制、断链联锁、故障判定、认证、持久化、报告和生产打包存在 P0/P1 阻断。修复 P0 前不建议上真实台架或连接车辆。
""",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


required_docs = [
    "AUDIT_INDEX.md", "00_EXECUTIVE_SUMMARY.md", "01_PROJECT_BASELINE.md", "02_UI_FIDELITY_AUDIT.md", "03_PAGE_FUNCTION_AUDIT.md",
    "04_FRONTEND_ARCHITECTURE_AUDIT.md", "05_BACKEND_API_AUDIT.md", "06_CAN_DBC_PROTOCOL_AUDIT.md", "07_SIMULATION_E2E_AUDIT.md",
    "08_EOL_TEST_ENGINE_AUDIT.md", "09_DATABASE_LOG_REPORT_AUDIT.md", "10_SECURITY_SAFETY_AUDIT.md", "11_TEST_QUALITY_AUDIT.md",
    "12_PERFORMANCE_RELIABILITY_AUDIT.md", "13_PACKAGING_DEPLOYMENT_AUDIT.md", "14_ISSUE_REGISTER.md", "15_REMEDIATION_PLAN.md",
    "audit_results.json", "issue_register.csv",
]

manifest_rows = []
for path in sorted(AUDIT.rglob("*")):
    if not path.is_file() or path.name == "AUDIT_MANIFEST.md":
        continue
    manifest_rows.append([path.relative_to(AUDIT).as_posix(), path.stat().st_size, sha256(path)])

write(
    "AUDIT_MANIFEST.md",
    f"""
# 审计清单

- 生成时间：{AUDIT_TIME}
- 文档要求文件：{len(required_docs)} 个，均由最终校验再次检查。
- 证据和审计文件总数（不含本清单）：{len(manifest_rows)}。
- 哈希：SHA-256；原始证据未在报告生成阶段删除。

{md_table(["路径", "字节", "SHA-256"], manifest_rows)}

`AUDIT_MANIFEST.md` 为自描述文件，不记录自身哈希。外部入口 `../AUDIT_REPORT.md` 由最终校验单独检查。
""",
)


print(
    json.dumps(
        {
            "audit_dir": str(AUDIT),
            "documents": len(required_docs) + 1,
            "evidence_and_files": len(manifest_rows),
            "ui_average": ui_average,
            "functional_completion": functional_completion,
            "real_completion": real_completion,
            "issues": dict(severity_counts),
        },
        ensure_ascii=False,
        indent=2,
    )
)
