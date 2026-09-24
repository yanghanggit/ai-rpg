# AI 代理 API 走查 CLI（run_agent_api.py）

---

## 定位

`scripts/run_agent_api.py` 是**取代原 TUI** 的服务器 API 走查入口，面向 **AI 代理**：
通过 HTTP 逐步驱动常驻的游戏服务端（`run_game_server.py`），供代理（或开发者）观察状态、
触发动作、逐条验证接口契约。

它**不是**产品客户端。正式玩家入口是独立仓库的 Web 客户端（`ai-rpg-web`），
后端是服务端真相所在，前端只消费同一套 HTTP 契约（靠 `/openapi.json` 生成类型）。
因此本项目内的 API 走查职责，天然由代理承担。

它与 `run_agent_game.py` 构成一对，区别在「通过哪一层操作游戏」：

| | `run_agent_game.py` | `run_agent_api.py` |
| --- | --- | --- |
| 交互层 | 进程内直接调 `ai_rpg.services.*` | 走 HTTP（`ai_rpg.api_agent.server_client`） |
| 状态位置 | 本地快照 `.worlds/...`（一次性进程） | 服务端**内存**（常驻进程） |
| 前提 | 无服务器 | 需 `run_game_server.py` 在跑 |
| 用途 | 服务层规则的无状态、可回溯验证 | HTTP 契约走查、交互式探索与边界试探 |

---

## 为什么移除 TUI

TUI 的职责只有「给后端开发者走查接口」，而这一职责已被两端取代：正式 UX 归 `ai-rpg-web`，
开发者走查归 AI 代理。更关键的是，TUI 是唯一让代理**无法介入**的组件：

- 全屏交互程序（Textual）需要独占 TTY（`isatty`、raw mode、alternate screen buffer）；
- 代理的终端工具是「一次性、面向行、基于管道」的，既无法注入按键，也无法从转义码流还原屏幕；
- `app.run()` 还会阻塞事件循环。

而 HTTP 路线没有这个问题：服务端只是监听 socket 的后台进程，CLI 只是一次性 HTTP 请求，
**全程不涉及 TTY**。

---

## 用法

```bash
export AI_RPG_API_HOST=127.0.0.1 AI_RPG_API_PORT=8000
export AI_RPG_USER=alice AI_RPG_GAME=Game1

uv run python scripts/run_agent_api.py login
uv run python scripts/run_agent_api.py new-game
uv run python scripts/run_agent_api.py status            # 观测 + suggested_actions
uv run python scripts/run_agent_api.py home enter-dungeon --dungeon "副本.坍塌庙祠"
uv run python scripts/run_agent_api.py opening init
uv run python scripts/run_agent_api.py opening generate-spoils
uv run python scripts/run_agent_api.py opening pick-spoils-card --actor 角色.无名 --card 沉马
uv run python scripts/run_agent_api.py dungeon advance-stage
uv run python scripts/run_agent_api.py combat init
uv run python scripts/run_agent_api.py combat draw-cards
uv run python scripts/run_agent_api.py combat play-cards --actor 角色.无名 --card 基础攻击 --target 怪物.纸人
uv run python scripts/run_agent_api.py combat pass-turn --actor 角色.无名
```

命令分组：顶层（`login`/`logout`/`new-game`/`status`/`dungeon-list`/`blueprint-list`/`compact`）、
`home`、`dungeon`、`opening`、`combat`。

### 约定

- **统一 JSON 输出**：成功为 `{"ok": true, "action", "result"}`；失败为
  `{"ok": false, "action", "detail"/"error", ...}` 并以**非零退出码**结束。
  HTTP 4xx/5xx 的 `detail` 原样透出，代理可据此自我纠错。
- **异步动作自动等待**：凡服务端返回 `job_id` 的动作，CLI 内部用 SSE 等到终态再输出，
  代理无需自行轮询。
- **状态在服务端**：本工具不缓存任何世界状态，也不读取 `.worlds/`；每次动作前建议先 `status`。
- **身份（L1）**：只通过 `--user/--game`（或环境变量）寻址，不落盘任何对局状态。
  注意 `/api/login/v1/` 会**清掉该 user 已有房间**，故只在开新局时调用一次。

---

## 观测（status）与流程推断（suggested_actions）

`status` 是核心，把原 TUI 分散在各 Screen 的取数逻辑收拢成一次结构化快照：
当前模式（家园/副本）、所在场景与角色、角色属性/手牌、副本房间与初始化标记、
开场奖励候选、战斗状态与最近回合、家园队伍/背包/储物箱、会话消息。

并在 `suggested_actions` 中给出下一步建议，沉淀的正是原本编码在 TUI 路由里的流程知识：

- **家园**：`advance` / `speak` / `switch-stage` / `generate-dungeon` / `enter-dungeon` /
  `roster-*` / `item-*` / `craft-*` / `wear-costume` / `compact`。
- **开场房间**：未初始化 → `opening-init`；未生成奖励 → `generate-spoils`；
  否则逐个候选卡 `pick-spoils-card`，以及 `advance-stage`。
- **战斗房间**：`INITIALIZATION` → `combat-init`；`ONGOING` 且未抓牌/回合已结束 →
  `draw-cards`；轮到某角色 → `play-cards`/`pass-turn`/`use-consumable`/`equip-gear`
  （怪物回合由服务端自动决策）；`COMPLETE`/`POST_COMBAT` → `collect-loot` /
  `advance-stage`（有下一关时）/ `exit-dungeon`。

建议只是提示，**以服务端校验为准**。

---

## 与回归测试的分工

代理动态走查**不可复现**（依赖 LLM 判断），不能取代固定回归：

- **契约 / 回归** → `tests/integration/test_api_e2e_smoke.py`（后端）与 `ai-rpg-web` 的
  Vitest + MSW（前端）；
- **探索 / 新特性走查 / 边界试探 / 交互式调试** → 代理 + `run_agent_api.py`。

---

## 目录结构

```
src/ai_rpg/api_agent/
  config.py         # ServerConfig / server_config（host/port 由 CLI 注入）
  server_client.py  # 全部 HTTP 接口封装（含 SSE 任务等待）
  status.py         # build_status：一次调用产出世界状态快照
  flow.py           # suggest_actions：由状态推断下一步
scripts/run_agent_api.py  # Click CLI（薄壳）
```
