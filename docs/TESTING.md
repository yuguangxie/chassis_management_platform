# 测试

运行 `pytest backend/tests -q`、`pytest simulator/tests -q`、`npm --prefix desktop run typecheck`、`npm --prefix desktop run build`。

# 数据生命周期工作包

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_data_lifecycle.py -q
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_storage_lifecycle_api.py -q
backend\.venv\Scripts\python.exe scripts/check_report_dependencies.py
```

测试只使用 pytest 临时目录、临时 SQLite 和 VirtualPrintBackend。禁止把测试的 `data_root` 指向用户现有目录，也禁止在本工作包中连接真实 CAN 或打印机。
