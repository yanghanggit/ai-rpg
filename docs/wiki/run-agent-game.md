# AI 操作 CLI（ai-rpg-agent-game）

---

## 设计定位

`ai-rpg-agent-game`（源码 `ai_rpg/cli/agent_game.py`）是专门面向 **AI 代理**（而非人类玩家）的游戏操作入口。正式玩家入口是独立仓库的 Web 客户端（`ai-rpg-web`），它连接常驻的游戏服务端（`ai-rpg-server`，由服务端持有游戏实例并跨请求维持状态）；服务器 API 的走查则交给 `ai-rpg-agent-api`。而本脚本不经过该服务端，直接通过本脚本进行**无状态、快照驱动**的推进。

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

`ai_rpg/cli/agent_game.py`（入口 `ai-rpg-agent-game`）只负责 Click 层：参数解析、日志初始化、世界恢复与存档路径构造。“存档复位 → 触发动作 → pipeline 推进 → 归档新存档”这套流程按游戏模式拆分到 `ai_rpg/game_agent/` 包内的动作模块：`core.py`（游戏实例创建/复位等共享基础设施）、`home.py`（家园剧情推进、对话、场景切换、副本生成、队伍名单）、`dungeon.py`（副本生命周期：进入/下一关/退出）、`opening.py`（副本开场房间：初始化、奖励生成与领卡）、`combat.py`（副本战斗动作，含战斗房间初始化）、`items.py`（背包道具移动、合成、时装）、`compact.py`（记忆压缩）。

这些动作模块本身只是薄封装，真正的游戏规则校验与 ECS 动作触发集中在 `ai_rpg.services.*`（如 `home_actions.py`、`dungeon_combat_actions.py`，以及副本生命周期按阶段拆分的 `dungeon_setup_action.py` / `dungeon_enter_action.py` / `dungeon_advance_action.py` / `dungeon_exit_action.py` / `dungeon_teardown_action.py` / `dungeon_archive_action.py`）。这一层与 CLI 完全解耦，同时被面向 Web 客户端的游戏服务端（`home_api.py`、`dungeon_lifecycle_api.py`、`dungeon_combat_api.py`、`dungeon_combat_tasks.py`）及测试套件直接复用——真正的复用边界在 `services` 层，而非 CLI 脚本本身。

---

## 状态机与命令可用性

脚本的命令集对应游戏的**两种模式**，命令本身即是状态机的边界声明：

- **家园模式**：`advance` / `speak` / `switch-stage` / `enter-dungeon` 等
- **副本模式**：`combat-init` / `opening-init` / `draw-cards` / `play-cards-specified` / `use-consumable` / `equip-gear` / `exit-dungeon` 等

其中副本房间的推进严格对齐服务端 API 的两步式调用：

1. `enter-dungeon` / `next-dungeon` 只负责**传送/推进房间**（对应 `/api/home/enter_dungeon/v1/` 与 `/api/dungeon/progress/advance_stage/v1/`），不初始化新房间；
2. 房间初始化需由代理根据新房间类型再显式发起一步：战斗房间用 `combat-init`（对应 `/api/dungeon/combat/init/v1/`），开场房间用 `opening-init`（对应 `/api/dungeon/opening/init/v1/`）。

### 战斗回合的推进粒度：出牌 ≠ 过牌

战斗内每个角色的**行动窗口**都只由显式 `pass-turn` 关闭；出牌、用消耗品、装备物化都不结束窗口：

- `play-cards-specified` 只打出一张牌，**不交出行动权**；`use-consumable` / `equip-gear` 同样不推进。
- `pass-turn --actor X` 把 X 记入本回合 `completed_actors`、清空其剩余能量并推进 `current_actor`；当所有存活角色都已过牌，本回合结束，需再次 `draw-cards` 开启下一回合。
- 该规则**对我方与怪物同等适用**。轮到怪物时，`play-cards-specified --actor 怪物.X` 触发其 AI 决策（选一张牌或过牌）：
  - AI **决定出牌** → 行动权仍在该怪物，需再执行 `pass-turn --actor 怪物.X` 才交出行动权；
  - AI **决定过牌** → 系统在同一次调用内已完成过牌，此时**不要**再对该怪物 `pass-turn`（它已不是当前行动者，调用会失败）。

因此代理的稳定做法是：每执行一个战斗动作后重新读取 `current_actor`，再据此选择下一步。`ai_rpg/api_agent/flow.py::suggest_actions` 对当前行动者同时给出 `play-cards` 与 `pass-turn` 两种建议，即体现这一协议；服务端本地任务层的 `execute_pass_turn_task` 也接受任意角色名。

→ 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md) 的「回合（Round）与行动（turn）」。

AI 代理无需感知内部游戏对象，只需根据当前存档的模式选择合法命令；`services` 层的前置条件校验失败时直接返回错误，动作模块据此提前 return，不会调用归档、不产出损坏存档。

---

## 卡牌原型的开发循环

改动 `demo/card_skeletons.py` / `demo/card_prototypes.py` 或词缀设计规范后，若想反复观察「角色 agent 把原型设计成了什么」，完整的 `scripts/setup_demo.py` 太重——它会 drop 数据库并重刷蓝图 / 副本 / RAG；开发循环只需要「把原型刷进库」这一小步。

`scripts/flush_card_prototypes.py` 就是这一步：只 upsert 原型（可选默认牌单），并逐条打印「新增 / 更新 / 未变」与变化的字段；`--only` / `--card-type` 收敛刷写范围，`--prune` 把库收敛到指定集合，`--dry-run` 只看不写。

关键能力是 `--prune`：库被收敛成「只剩要测的原型」后，`generate-spoils` 的随机抽样退化为确定抽样，于是可以定点复现同一原型的词缀设计。观测端配 `scripts/inspect_spoils.py`，它打印某个快照里 Spoils 候选的完整字段与逐条词缀的校验结果。

循环形态：改原型 → 刷库 → 对停在开场房间的存档 `generate-spoils` → 读设计结果与 `.chat_dumps`。`--prune` 只影响其它仍从库读原型的流程（默认牌单物化、工坊示例检索），重跑一次全量刷即可恢复。

---

## 日志追溯

每次调用生成独立日志文件，路径为 `logs/run_agent_game_{timestamp}.log`，时间戳与新存档一致，便于将一条存档与其对应的完整执行日志一一对应。
