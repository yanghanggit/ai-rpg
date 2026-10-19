# 副本生成管道（Dungeon Generation Pipeline）

---

## 核心哲学

副本生成与工坊合成共享同一架构原则：**机制与内容彻底分离**。整个管道的 prompt 模板不包含任何世界观相关的故事内容——副本主题、生态底色、场景氛围、生物特征全部通过系统消息注入。换一套战役设定与角色规范，管道代码无需任何修改。

副本的**结构**（房间数、每房间怪物数、必有 1 个开场房间）由代码常量固定，不交给 LLM 决定；数值作为**任务提示词的输入数据**下发到对应步骤——Step 2 拿到房间总数与开场 / 战斗拆分，Step 3 拿到每个战斗房间的怪物数——工具 schema 的 `minItems` / `maxItems` / `enum` 据此构建。副本生成实体的 system prompt **不含任何数量**，容器与执行侧由此解耦（见下文「结构常量」）。

→ 参见：[工坊合成管道（Craft Pipeline）](craft-pipeline.md)

---

## 为何是接力管道而非单步调用

副本涉及多层创作——整体设定、逐个房间、每个房间的怪物、怪物牌库——且后一层依赖前一层的产出。因此设计为多步 `ReactiveProcessor` 接力：

- 所有步骤都由同一个 `GenerateDungeonAction`（挂「世界.副本生成系统」实体）触发，按 `create_dungeon_generate_pipeline` 的注册顺序依次执行，共享一份内存中间数据 `DungeonDraft`（挂 `game._dungeon_draft`）。
- 每步把产物写入两条通道：
  1. **Agent Memory（LLM 记忆）**：Step 1–3 的 prompt / AI 回复 / 工具结果原地追加到副本生成实体的持久化记忆，后续步骤的 LLM 直接继承前序创作，保持叙事连贯。例外是 Step 0：世界导演的 Q&A 写入导演实体自己的 memory，指令经 `DungeonDraft.directive` 传入 Step 1。
  2. **DungeonDraft（控制流数据）**：确定性字段（房间数、房间列表、怪物列表）在内存流转，供代码构建工具 schema 与组装实体。
- Step 4 才把最终副本（`Dungeon`）与草稿写入磁盘；流程末尾由 `DungeonGenerationCleanupSystem` 清空 `DungeonDraft` 并重置生成实体记忆。

---

## 分步分工与设计意图

**Step 0 — 世界导演指令**（`GenerateDungeonDirectiveSystem`）。世界导演推理一条创作指令，写入 `DungeonDraft.directive`。执行方实体名（携带 `GenerateDungeonAction` 的那个世界实体）由引擎注入任务提示词，世界导演的 system prompt 不写死任何实体名——实体改名不会让 prompt 静默失效。

**Step 1 — 副本设定生成**（`GenerateDungeonProfileSystem`）。单次 `agent_loop`（调用 `record_dungeon_profile`）锁定副本名称与整体设定（`profile`）。房间总数当前不由 LLM 决定：handler 直接回填默认值 `DEFAULT_DUNGEON_ROOM_COUNT`（未来由房间组合规划决定）。设定刻意回避角色身份与评价性词汇，只呈现感官与情境细节。

**Step 2 — 房间设计**（`GenerateDungeonRoomsSystem`）。在同一 agent 记忆内一次性生成全部房间：前 `DEFAULT_OPENING_ROOM_COUNT` 个强制为开场（`room_type = "opening"`），纯氛围描写；其余为战斗房间（`room_type = "combat"`）。开场 / 战斗拆分与每个战斗房间的 `actor_count` 当前都取默认值（`DEFAULT_MONSTERS_PER_COMBAT_ROOM`）；提示词与工具 schema 的开场数同样取自 `DEFAULT_OPENING_ROOM_COUNT`，不用「总数减一」推断。产物写入 `DungeonDraft.rooms`。

**Step 3 — 怪物生成**（`GenerateDungeonActorsSystem`）。单次 `agent_loop`：LLM 可在一个 response 内并行、也可分多次调用 `record_dungeon_actor`（每次创建一个怪物），每个怪物用 `room_name` 显式声明归属房间。handler 累积，代码严格校验「归属合法」且「每个 combat 房间数量 == 固定值」。产物写入 `DungeonDraft.actors`。

**Step 4 — 实体组装**（`AssembleDungeonSystem`）。零 LLM 调用，纯确定性映射。根据 `room_type` 分发：`"opening"` → `OpeningRoom`，`"combat"` → `CombatRoom`（含 Stage + Actor）。产物 `Dungeon` 写入 `.dungeons/<name>.json`，同时把 `DungeonDraft` 落一份到 `.dungeons_drafts/<name>.json` 便于回溯。

**Step 5 — 牌库组建**（`AssembleDungeonDeckSystem`）。为每个战斗房间的怪物组建初始牌库：怪物先从手牌原型库选 5 个骨架（`select_cards`），再由卡牌设计引擎设计（见[卡牌设计指南（Card Design）](card-design.md) 的「生成契约」）。两阶段都走 `card_common` 的 actor 上下文入口：宿主是世界实体「世界.卡牌设计」，上下文 = 它的 `role_rules`（system）+ 怪物自己的 system prompt（任务数据块），会话不留痕；失败回退默认牌单。完成后重写 `.dungeons/<name>.json`。

**Step 6 — 场景插画**（`IllustrateDungeonSystem`）。加载磁盘上的 `Dungeon`，交给「世界.插图提示词」世界实体（`IllustrationComponent`）作为 agent，依据各场景设定与生物外观一次性编排封面 + 各房间的文生图提示词（工具 `record_image_prompts`）。引擎只负责传递事实与调用 replicate 批量出图，画风、构图与负面词全部由该实体的 system prompt 承载（故事层）。生成失败项保持 `None`，不阻塞主流程。

---

## 结构默认值

`models/dungeon_draft.py` 定义副本结构的**默认值**（不是不变量）：未来由 LLM 按自身的创作原则与判断决定房间组合，开场房间默认且通常恒为 1，战斗房间数与每房间怪物数可变化，代码只负责保底与校验边界。它们在运行时由各步的任务提示词与工具 schema 消费；`demo/world.py` 不引用这些默认值：

| 默认值 | 含义 |
| --- | --- |
| `DEFAULT_OPENING_ROOM_COUNT` | 默认开场房间数（无战斗，纯门口氛围） |
| `DEFAULT_COMBAT_ROOM_COUNT` | 默认战斗房间数 |
| `DEFAULT_MONSTERS_PER_COMBAT_ROOM` | 默认每个战斗房间的怪物数 |
| `DEFAULT_DUNGEON_ROOM_COUNT` | 默认副本房间总数 = 开场 + 战斗 |

改默认值只需改这些常量——数量不进 blueprint，因此无需重刷蓝图（`python -m scripts.setup_demo`）；只有同时改了 `demo/` 文案才需要刷新。

---

## 数据流一览

- Step 0 directive → `DungeonDraft.directive`
- Step 1 profile → `DungeonDraft.dungeon_name` / `profile` / `room_count`
- Step 2 rooms → `DungeonDraft.rooms`（`List[DungeonRoomDraft]`）
- Step 3 actors → `DungeonDraft.actors`（`List[DungeonActorDraft]`）
- Step 4 组装 → `.dungeons/<name>.json` + `.dungeons_drafts/<name>.json`
- Step 5 牌库 → 回写 `.dungeons/<name>.json`（各怪物 `DeckComponent`）
- Step 6 从磁盘加载 Dungeon →「世界.插图提示词」编排提示词 → replicate 出图 → 写回 `dungeon.assets["cover"]` / `stage.assets["illustration"]`（仅落 `.assets/image/<file>.meta` 地址，`ImageMeta` 不内连）
- 收尾：`DungeonGenerationCleanupSystem` 清空 `DungeonDraft` 并重置生成实体记忆

---

## 中间数据模型（`models/dungeon_draft.py`）

| 模型 | 说明 |
| --- | --- |
| `DungeonRoomDraft` | 单个房间：`room_type` / `room_name` / `profile` / `actor_count` |
| `DungeonActorDraft` | 单个怪物及其归属房间：`room_name` / `actor_name` / `profile` / `base_body` |
| `DungeonDraft` | 整条流程的内存中间数据：`directive` / `dungeon_name` / `profile` / `room_count` / `rooms` / `actors` |

---

## 设计决策

| 决策 | 理由 |
| --- | --- |
| 首房间强制为 opening 房间 | 副本开场需要叙事铺垫，与战斗房间职责分离 |
| `room_type` 显式声明房间类型 | 避免以 `actor_count` 等间接字段推断类型，扩展新房间类型只需加 Literal 值 |
| 房间总数与每房间怪物数有默认常量保底 | 当前结构可控、便于测试与调试；未来交给房间组合规划，数量作为任务提示词输入下发，工具 schema 据此构建，system prompt 不含数量 |
| Step 2 一次性生成全部房间 | 房间间的递进关系需要同一记忆 |
| Step 3 单 agent_loop 多次工具调用 | 一个 response 可并行发多个 `record_dungeon_actor`，每次调用原子清晰，无需并发编排 |
| agent memory 添加式传递 | 后续步骤 LLM 继承前序创作，保持叙事连贯 |
| `DungeonDraft` 传递控制流数据 | 确定性字段（房间数、房间列表、怪物列表）供代码构建工具 schema 与组装，不经 LLM 文本解析 |
| Step 4 零 LLM 调用 | 组装是纯结构映射，无需创意决策 |
| 牌库组建以怪物自身 system prompt 为唯一临时上下文 | 牌是「怪物自己的」，与副本生成实体的持久记忆隔离，选完即弃 |

---

## 房间类型

| room_type | DungeonRoom 子类 | 说明 | 可扩展 |
| --- | --- | --- | --- |
| `opening` | `OpeningRoom` | 开场，无战斗，纯场景氛围 | — |
| `combat` | `CombatRoom` | 战斗房间，含怪物与预置卡牌 | — |
| *(future)* | *(TBD)* | 如 puzzle、treasure 等 | 新类型只需追加 Literal + DungeonRoom 子类 |
