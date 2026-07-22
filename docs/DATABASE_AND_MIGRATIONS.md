# SQLite、Migration 与恢复

当前 schema version 为 3，可通过 `GET /api/v1/storage/schema-version` 查询。

## 版本定义

| 版本 | 内容 |
|---|---|
| 1 | 检测会话、步骤、断言、CAN/信号、告警、报告、账户、session、override、配置与操作审计基础表 |
| 2 | 检测方案、安全停车和断言质量/来源元数据兼容升级 |
| 3 | 报告归档、打印 spooler 字段、备份记录、cleanup job 与索引 |

`schema_migrations` 保存 version、名称、checksum 和 UTC 应用时间，并同步 `PRAGMA user_version`。升级函数先检查列是否存在，因此重复执行安全；数据库版本高于软件支持版本时拒绝启动。

## 新库与旧库

新库按 1→2→3 顺序创建。没有 `schema_migrations` 的旧库从 0 开始执行幂等建表/补列。已标记 v1 或 v2 的库只执行后续版本。每次升级已有业务 schema 前，都会在 `<data_root>/backups/migration` 创建 SQLite 一致性备份。

若 migration 抛出异常，事务回滚、连接关闭，并用升级前备份恢复主文件；启动仍返回明确失败，避免以未知 schema 继续运行。测试覆盖新库、v1、v2、重复执行、注入失败和恢复。

## 数据库故障规则

- `BEGIN IMMEDIATE` 或 commit 失败会触发数据库故障回调。
- `writable()` 使用 TEMP 表，不在业务库持续累积探针记录。
- `integrity_check != ok` 一律视为阻断状态。
- 业务写入失败必须向上抛出；不得把未落库会话、报告、清理或打印动作报告为成功。

SQLite 文件不允许用资源管理器热复制作为正式备份；必须调用平台 online backup API。
