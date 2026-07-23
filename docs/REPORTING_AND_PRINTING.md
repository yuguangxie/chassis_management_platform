# 报告生成、PDF 与 Windows 打印

## 2026-07-23 追溯元数据

报告使用运行时真实 software release、clean commit、config version/hash、DBC hash、test-plan version/hash、车型、工位、operator/principal 与 EOL identity；DBC/release 不可用时显示未知/null，不使用固定 hash、数量或请求当前时间。打印审计继续绑定操作员、报告 hash、spooler job id 和状态。Windows 真实打印机、卡纸/脱机/驱动差异仍是外部现场验收项；本工作包只运行虚拟打印后端测试。

## 四种正式输出

报告生成器回归覆盖 JSON、DOCX、PDF、CSV。JSON 是最小必需格式；任一格式失败会记录独立状态和错误，并删除该格式半成品。报告数据库记录保存文件大小和 SHA-256。

当前 PDF 使用 ReportLab 原生渲染，DOCX 使用 python-docx，两者独立生成。系统不会重命名 DOCX、HTML 或文本文件冒充 PDF。PDF 预览使用 PyMuPDF。

`configs/report_config.yaml` 明确：

- `pdf_renderer: reportlab-native`；
- `docx_to_pdf_converter: disabled`。

若项目以后要求“以 DOCX 为唯一版式再转换 PDF”，必须把 converter 改为 `libreoffice` 或 `word`，随安装包提供依赖，并先运行：

```powershell
backend\.venv\Scripts\python.exe scripts\check_report_dependencies.py
```

缺少 converter 时检查脚本返回非零和可执行修复建议，不生成伪 PDF。当前原生 PDF 模式同样检查 python-docx、ReportLab 和 PyMuPDF。

## 打印状态机

```text
QUEUED → PRINTING → COMPLETED
   └──────────────→ FAILED → retry → QUEUED
QUEUED/PRINTING ─→ CANCELLED → retry → QUEUED
```

打印前必须选定已存在 PDF、完成预览确认并计算报告 SHA-256。持久化 job 后才向 spooler 提交，保存 printer、backend、spooler job id、hash、attempts、状态详情和 UTC 时间。后台 monitor 每 2 秒同步非终态任务；UI 不打开时状态仍会更新。

dev/mock/test 默认使用显式 `virtual` backend；production 禁止 virtual，使用 Windows spooler。Windows 实现依赖 pywin32，以 RAW PDF 提交，因此现场打印机驱动必须支持 PDF passthrough。配置要求打印机时，production 启动会检查枚举能力并 fail-closed。

CI 使用 VirtualPrintBackend 验证 queued、completed、failed、cancelled 和 retry，不依赖真实打印机。
