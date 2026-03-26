# TUI 客户端开发日志

> 分支：`feat/tui-client-dev`  
> 日期：2026-03-26

---

## 模块结构

```text
src/ai_rpg/tui_client/
├── __init__.py             # 导出 GameClient
├── app.py                  # GameClient(App) 主应用，负责启动和连接服务器
├── server_client.py        # 游戏服务器 HTTP 客户端（httpx 异步封装）
└── screens/
    ├── __init__.py         # 导出 MainMenuScreen / NewGameScreen
    ├── main_menu.py        # MainMenuScreen：主菜单（1 新游戏 / q 退出）
    └── new_game.py         # NewGameScreen：新游戏表单
```

---

## 启动脚本

```text
scripts/run_tui_game_client.py
```

从 `ai_rpg.tui_client` 导入 `GameClient` 并运行，自身保持精简；支持 `--web` 浏览器模式。

---

## 运行流程

```text
GameClient.on_mount()
  └─ connect_to_server() [Worker]
       ├─ 失败 → RichLog 显示 ❌ 连接失败
       └─ 成功 → switch_screen(MainMenuScreen)
                    └─ 输入 "1" → push_screen(NewGameScreen)
                                    ├─ 填 user_name（默认 player_{timestamp}）
                                    ├─ 填 game_name（默认 Game1）
                                    └─ Enter → login() → new_game()
                    └─ 输入 "q" → app.exit()
```

---

## server_client.py API 列表

| 函数 | HTTP | 路径 | 说明 |
| ------ | ------ | ------ | ------ |
| `fetch_server_info()` | GET | `/` | 检查服务器连通性 |
| `login(user_name)` | POST | `/api/login/v1/` | 登录，返回 message 字符串 |
| `new_game(user_name, game_name)` | POST | `/api/game/new/v1/` | 创建新游戏，返回完整响应 JSON |

服务器地址：`http://192.168.192.102:8000`（写死，快速开发阶段）

---

## 设计决策

- **Textual Screens 方案**：每个 UI 状态对应一个独立 `Screen`，扩展性好
- **`@work` 装饰器**：所有异步 HTTP 调用均通过 Textual Worker 执行，避免阻塞 UI 线程
- **游戏蓝图（game_name）**：本期手动输入，默认 `Game1`，不拉取蓝图列表
- **app.py 职责极简**：只保留 Header + 启动日志 RichLog + Footer，内容区全部由 Screen 承载

---

## mypy strict 注意事项

详见 [python-mypy-strict.md](./python-mypy-strict.md)
