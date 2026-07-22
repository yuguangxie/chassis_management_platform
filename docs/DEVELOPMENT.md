# 开发说明

后端使用 FastAPI + asyncio，前端使用 Electron + Vue 3 + TypeScript，仿真器使用 UDP 模拟以太网转 CAN。

默认开发边界是 `127.0.0.1`。复制 `.env.example` 中需要的非秘密变量到本机运行环境；不得填写或提交真实账号、现场 endpoint、bootstrap secret、配置签名 key 或 session token。`python scripts/dev_backend.py` 消费统一 host/port/profile；非 production 使用非回环地址会拒绝启动。

首次启动若账户库为空，后端在 `<CHASSIS_DATA_DIR>/auth/bootstrap-admin.secret` 创建一次性随机凭据并只记录文件路径。使用登录页初始化管理员后文件自动删除。测试/E2E 每次运行动态生成 bootstrap、密码、签名 key 和短期会话，不使用固定开发 token。

接口或权限变更后运行 `python scripts/generate_api_docs.py`，并提交生成的 `docs/openapi.json`、`docs/api-authorization-matrix.csv` 和配置 schema。
