# 副本生成管道（Dungeon Generation Pipeline）

---

## 核心哲学

副本生成与工坊合成共享同一架构原则：**机制与内容彻底分离**。整个管道的 prompt 模板不包含任何世界观相关的故事内容——副本主题、生态底色、场景氛围、生物特征全部通过系统消息注入。换一套战役设定与角色规范，管道代码无需任何修改。

→ 参见：[工坊合成管道（Craft Pipeline）](craft-pipeline.md)

---

## 为何是接力管道而非单步调用

副本涉及三层创作——整体设定、逐个房间、每个房间的怪物——且后一层依赖前一层的产出。因此设计为多步 `ReactiveProcessor` 接力，每步完成时把产物写入两条通道，并替换实体上的 Action 组件触发下一步：

1. **Agent Context（LLM 记忆）**：Step 1–3 的 prompt / AI 回复 / 工具结果原地追加到副本生成实体的持久化上下文，后续步骤的 LLM 直接继承前序创作，保持叙事连贯。例外是 Step 0：世界导演的 Q&A 写入导演实体自己的 context，指令经 Action 组件字段（`GenerateDungeonDirectiveAction.directive`）传入 Step 1，而非写入副本生成实体 context。
2. **Action 组件（控制流数据）**：确定性字段（房间数、房间列表、蓝图）经 Action 组件传给下一步，供代码构建工具 schema 与组装实体。

Step 0–3 之间不再写任何中间 JSON 文件，数据全在内存流转；Step 4 才将最终副本（Dungeon）与调试蓝图（DungeonBlueprint）写入磁盘。

---

## 分步分工与设计意图

**Step 0 — 世界导演指令**（`GenerateDungeonDirectiveSystem`）。世界导演推理一条创作指令，挂 `GenerateDungeonDirectiveAction`。

**Step 1 — 副本设定生成**（`GenerateDungeonProfileSystem`）。单次 `agent_loop`（调用一次 `record_dungeon_profile` 工具）锁定副本名称、整体设定（`dungeon_profile`）与房间总数（`dungeon_room_count`，含 1 个入口房间）。设定刻意回避角色身份与评价性词汇，只呈现感官与情境细节。产物挂 `GenerateDungeonRoomsAction`。

**Step 2 — 房间设计**（`GenerateDungeonRoomsSystem`）。在 Step 1 的同一 agent 上下文内一次性生成全部房间。首房间强制为叙事入口（`room_type = "entry"`），纯氛围描写；其余为战斗房间（`room_type = "combat"`）。同上下文保证入口到深处的叙事递进。产物 `rooms: List[DungeonRoomData]` 挂 `GenerateDungeonActorsAction`。

**Step 3 — 怪物生成**（`GenerateDungeonActorsSystem`）。单次 agent_loop：LLM 可在一个 response 内并行、也可分多次调用 `record_dungeon_actor`（每次创建一个怪物），每个怪物用 `room_name` 显式声明归属房间。handler 累积，代码严格校验「归属合法」且「每个 combat 房间数量 == `actor_count`」。产物组装为 `DungeonBlueprint`，挂 `AssembleDungeonAction`。

**Step 4 — 实体组装**（`AssembleDungeonSystem`）。零 LLM 调用，纯确定性映射。根据 `room_type` 分发：`"entry"` → `EntryRoom`，`"combat"` → `CombatRoom`（含 Stage + Actor）。当前为所有怪物统一赋予「纯攻击型」战斗关键词——框架层行为预设，与故事内容无关。

Step 5（场景插画）已实现但未接入主管道，不阻塞副本基础可用性。`AssembleDungeonSystem` 仍会挂 `IllustrateDungeonAction`，但因 `IllustrateDungeonActionSystem` 未注册，该动作会在当轮 `ActionCleanupSystem` 中被清除，无副作用。

---

## 数据流一览

```text
Step 0  directive ── GenerateDungeonDirectiveAction ─▶
Step 1  profile   ── GenerateDungeonRoomsAction(dungeon_name, dungeon_profile, dungeon_room_count) ─▶
Step 2  rooms     ── GenerateDungeonActorsAction(dungeon_name, dungeon_profile, rooms) ─▶
Step 3  actors    ── AssembleDungeonAction(dungeon_name, blueprint) ─▶
Step 4  组装 Dungeon 实体树
```

---

## 中间数据模型（`models/dungeon_generation.py`）

两层语义、后缀统一：

| 层 | 模型 | 说明 |
| --- | --- | --- |
| Data（LLM 中间产物） | `DungeonRoomData`、`DungeonActorData` | LLM 工具调用的结构化产物 |
| Blueprint（组装蓝图） | `DungeonActorBlueprint`、`DungeonRoomBlueprint`、`DungeonBlueprint` | Step 4 组装所需的结构化蓝图 |

---

## 设计决策

| 决策 | 理由 |
| --- | --- |
| 首房间强制为 entry 房间 | 副本入口需要叙事铺垫，与战斗房间职责分离 |
| room_type 显式声明房间类型 | 避免以 actor_count 等间接字段推断类型，扩展新房间类型只需加 Literal 值 |
| 房间总数与角色数由 LLM 决定 | 硬编码会使不同规模的副本产出单一 |
| Step 2 一次性生成全部房间 | 房间间的递进关系需要同一上下文 |
| Step 3 单 agent_loop 多次工具调用 | 一个 response 可并行发多个 `record_dungeon_actor`，每次调用原子清晰，无需并发编排 |
| agent context 添加式传递 | 后续步骤 LLM 继承前序创作，保持叙事连贯 |
| Action 组件传递控制流数据 | 确定性字段（房间数、房间列表、蓝图）供代码构建工具 schema 与组装，不经 LLM 文本解析 |
| Step 4 零 LLM 调用 | 组装是纯结构映射，无需创意决策 |

---

## 房间类型

| room_type | DungeonRoom 子类 | 说明 | 可扩展 |
| --- | --- | --- | --- |
| `entry` | `EntryRoom` | 叙事入口，无战斗，纯场景氛围 | — |
| `combat` | `CombatRoom` | 战斗房间，含怪物与牌组 | — |
| *(future)* | *(TBD)* | 如 puzzle、treasure 等 | 新类型只需追加 Literal + DungeonRoom 子类 |
