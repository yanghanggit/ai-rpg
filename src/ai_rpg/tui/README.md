# TUI 测试客户端（开发用）

AI-RPG 的**开发用测试客户端**：基于 [Textual](https://textual.textualize.io/) 的终端界面，
供开发者在开发过程中**手动走查各 API 流程**（登录 → 家园 → 副本 → 战斗），
本质是仿制型客户端，**不面向正式玩家**。

- 以**斜杠命令**（`/xxx`）驱动，逐条触发后端接口并查看返回 / 仲裁结果。
- 分层：`utils`（根工具）→ `combat_data_access`（取数 + mock）→ `cmd_xxx`（命令逻辑）→ `*_screen`（页面）。
- 支持 `--dev-screen` 跳过登录、用本地 mock 数据离线走查（无需服务器）。

启动：`uv run python scripts/run_tui_client.py --server-host <HOST> --server-port <PORT>`
