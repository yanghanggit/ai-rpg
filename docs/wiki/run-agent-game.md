# AI 操作 CLI（run_agent_game.py）

---

## 设计定位

`run_agent_game.py` 是专门面向 **AI 代理**（而非人类玩家）的游戏操作入口。人类玩家通过 `run_tui_client.py` 作为 HTTP 客户端连接常驻的游戏服务端（`run_game_server.py`，由服务端持有游戏实例并跨请求维持状态）；AI 代理不经过该服务端，直接通过本脚本进行**无状态、快照驱动**的推进。

两者的根本区别：游戏服务端是长期运行的有状态进程，靠网络请求驱动；本脚本每次调用都是独立的一次性进程，直接读取本地存档 → 执行单次动作 → 写出新存档，进程退出后无任何残留状态，也不依赖服务端是否在运行。

---

## 快照驱动的意义

每条命令的结构固定为：**一个输入存档目录 → 一次动作 → 一个输出存档目录**。这使 AI 代理获得三项能力：

- **回溯**：任意保留历史快照，随时从旧状态重新推进，不需要撤销机制。
- **分支**：对同一快照多次调用不同命令，探索多条叙事路径而互不干扰。
- **可复现**：相同快照 + 相同命令，可以在任何环境重放操作序列。

存档按 `.worlds/{user}/{game}/{timestamp}/` 路径组织，时间戳即为本次操作的唯一标识。

---

## CLI 与动作逻辑的分层

`run_agent_game.py` 只负责 Click 层：参数解析、日志初始化、世界恢复与存档路径构造。"存档复位 → 触发动作 → pipeline 推进 → 归档新存档"这套流程按游戏模式拆分到四个动作模块：`agent_game_core.py`（游戏实例创建/复位等共享基础设施）、`agent_game_home.py`（家园模式动作）、`agent_game_combat.py`（地下城战斗动作）、`agent_game_inventory.py`（背包/合成/队伍管理动作）。

这四个模块本身只是薄封装，真正的游戏规则校验与 ECS 动作触发集中在 `ai_rpg.services.*`（如 `home_actions.py`、`dungeon_actions.py`、`dungeon_lifecycle.py`）。这一层与 CLI 完全解耦，同时被面向 TUI 客户端的游戏服务端（`home_gameplay.py`、`dungeon_tasks.py`）及测试套件直接复用——真正的复用边界在 `services` 层，而非 CLI 脚本本身。

---

## 状态机与命令可用性

脚本的命令集对应游戏的**两种模式**，命令本身即是状态机的边界声明：

- **家园模式**：`advance` / `speak` / `switch-stage` / `enter-dungeon` 等
- **地下城模式**：`draw-cards` / `play-cards-specified` / `use-consumable` / `use-gear` / `exit-dungeon` 等

AI 代理无需感知内部游戏对象，只需根据当前存档的模式选择合法命令；`services` 层的前置条件校验失败时直接返回错误，动作模块据此提前 return，不会调用归档、不产出损坏存档。

---

## 日志追溯

每次调用生成独立日志文件，路径为 `logs/run_agent_game_{timestamp}.log`，时间戳与新存档一致，便于将一条存档与其对应的完整执行日志一一对应。
