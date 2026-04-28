# 战斗管线（Combat Pipeline）

> 工厂函数：`create_combat_pipeline`  
> 源码：`src/ai_rpg/game/tcg_game_process_pipeline.py`  
> 上级入口：[[overview]]

---

## 适用场景

玩家进入**地牢**后触发此管线，持续运行直到战斗结束（胜利/失败）或玩家撤退。  
每一帧代表战斗中的**一次行动**（一个角色出一张牌），而非一整个回合。

---

## 回合生命周期

```text
[帧 N]  抽牌 → 敌方决策 → 叙事润色
         ↓
        一个角色出一张牌（PlayCardsAction）
         ↓
        仲裁结算 → 追加状态效果 → Stage 干预
         ↓
        检查胜负
         ↓
        回合清理 → 创建新回合
         ↓
[帧 N+1] ...
```

---

## 执行顺序

| 步骤 | System | 类型 | 职责 |
| ------ | -------- | ------ | ------ |
| 1 | `PrologueSystem` | Execute | 管线入口 → [[systems-shared#PrologueSystem]] |
| 2 | `ActorAppearanceUpdateSystem` | Execute | 生成角色外观 → [[systems-shared#ActorAppearanceUpdateSystem]] |
| 3 | `StageDescriptionSystem` | Execute | 生成场景描述（状态守卫：仅战斗开始时触发）→ [[systems-shared#StageDescriptionSystem]] |
| 4 | `CombatInitializationSystem` | Execute | 初始化战斗：注入战场上下文；第一回合由 `CombatRoundTransitionSystem` 在同帧末端创建 |
| 5 | `DrawCardsActionSystem` | Reactive | 为角色生成手牌（历史牌组 + LLM 新牌） |
| 6 | `EnemyPlayDecisionSystem` | Execute | 敌方 AI 决策出哪张牌 |
| 7 | `PlayActionNarrationSystem` | Execute | LLM 润色出牌叙事 |
| 8 | `PlayCardsActionSystem` | Reactive | 执行出牌，触发后续仲裁链 |
| 9 | `RetreatActionSystem` | Reactive | 处理撤退行动 |
| 10 | `ArbitrationActionSystem` | Reactive | **核心**：AI 仲裁伤害/格挡/HP 结算 |
| 11 | `AddActorStatusEffectsActionSystem` | Reactive | 为角色追加状态效果（最多 2 个/帧） |
| 12 | `PostArbitrationActionSystem` | Reactive | 双路径：Stage Agent 干预（追加效果 / 塞牌）；Actor 路径预留（暂为 stub） |
| 13 | `CombatRoundCompletionSystem` | Execute | 回合完成判定：所有存活角色 energy ≤ 0 时写入 `Round.is_completed = True` |
| 14 | `CombatOutcomeSystem` | Execute | 检测胜负：友方/敌方全灭则结算 |
| 15 | `CombatRoundCleanupSystem` | Execute | 清除旧回合手牌与格挡，递减状态效果 |
| 16 | `CombatRoundTransitionSystem` | Execute | 创建新回合，按速度排序生成行动顺序快照 |
| 17 | `CombatArchiveSystem` | Execute | 战斗归档：LLM 生成总结，压缩消息（状态守卫） |
| 18 | `ActionCleanupSystem` | Execute | 清理所有 Action → [[systems-shared#ActionCleanupSystem]] |
| 19 | `DestroyEntitySystem` | Execute | 销毁标记实体 → [[systems-shared#DestroyEntitySystem]] |
| 20 | `EpilogueSystem` | Execute | flush 状态 → [[systems-shared#EpilogueSystem]] |

---

## 核心系统详解

### CombatInitializationSystem（步骤 4）

**源码**：`src/ai_rpg/systems/combat_initialization_system.py`  
**类型**：`ExecuteProcessor`（含状态守卫）

**触发条件**：战斗序列状态为 `initializing`（尚未有任何回合记录时）。

执行内容（无 LLM 推理，纯上下文注入）：

- 向所有参战角色注入战场情境通知（场景名 / 场景描述 / 其他角色外观与阵营 / 自身属性）
- 以模拟 AIMessage 保证 agent 对话历史连续性
- 转换战斗状态为 `ONGOING`
- 为所有参战角色添加 `AddStatusEffectsAction`，触发初始状态效果评估
- **不**创建第一回合——Round 1 由同帧末端的 `CombatRoundTransitionSystem` 统一创建（见步骤 16）

参见 [[design-patterns#3. 状态守卫（State Guard）]]

---

### DrawCardsActionSystem（步骤 5）

**源码**：`src/ai_rpg/systems/draw_cards_action_system.py`  
**监听**：`DrawCardsAction`（`max_num_cards=3`）

**抄牌策略**（历史牌优先 + 保证新鲜度 + Keyword 约束 + 骨値注入 + Prompt 压缩）：

- 从 `DrawDeckComponent`（可重抄历史牌池）取最多 `max_num_cards - 1` 张（FIFO 消耗）
- 出牌时，仅 `card.source == actor_name` 的卡牌归入 `DiscardDeckComponent`（用于统计与展示）；`source` 不匹配的外来牌（含 Stage 塞入牌）直接丢弃，不归档
- 至少 1 张由 LLM 实时生成，结合角色当前属性（HP/攻击/防御）和状态效果
- 从 `KeywordComponent` 随机采样 `num_cards` 个关键词约束，逐张注入 prompt（详见下方）
- 每回合为每张牌生成一个 `DiceValue.MIN`～`DiceValue.MAX`（0-100）的随机整数（骰值），逐张附加在约束行末尾
- 两部分合并为最终手牌写入 `HandComponent`

每张牌包含：`name` / `description` / `damage_dealt` / `block_gain` / `hit_count` / `target_type` / `status_effect_hint`

**Keyword 关键词约束 + 骨値机制**：

每个角色携带 `KeywordComponent`（来自蔗图数据 `Actor.keywords`），定义若干自然语言约束规则。  
抄牌时系统随机采样 `num_cards` 个关键词（池够时无放回，不够时有放回），并同步生成等数量的骨値，在 prompt 中按位置逐张声明。骨値以 `（骨値：N）` 形式附于各卡约束行末，同时 prompt header 中包含匆底说明：若 `Keyword.description` 未说明骨値用法，LLM 应忽略该数字。

当 `keywords` 为空时，退回通用“差异化设计原则”提示（不附骨値），与改动前行为一致（向后兼容）。

详细设计：[[keyword-system]]

**Prompt 压缩**（`use_compressed_prompt`，默认开启）：对话历史只写入每轮变化的动态感知部分（回合编号、角色属性、Draw 状态效果、关键词约束与骰值），静态的字段说明与 JSON 格式示例以 `draw_cards_full_prompt` 附挂在消息额外字段中保留，LLM 推理仍使用全量版。

参见 [[design-patterns#4. 并行 LLM 推理]]

---

### 卡牌目标类型（CardTargetType）

`CardTargetType` 是每张卡牌的目标范围声明，由 `DrawCardsActionSystem` 在生成阶段由 LLM 写入 `target_type` 字段，再分别由玩家出牌路径（`dungeon_actions._resolve_targets`）和敌方 AI 路径（`EnemyPlayDecisionSystem._process_enemy_decision`）消费为实际 `targets` 列表，最终由 `ArbitrationActionSystem` 按列表逐目标结算伤害与格挡。

**六种目标类型**：

| 枚举值 | 目标范围 | `targets` 填写策略 |
|---|---|---|
| `enemy_single` | 单个敌方 | 调用方指定，列表长度 = 1 |
| `enemy_all` | 全体存活敌方 | 系统自动填所有存活敌人 |
| `enemy_random_multi` | 多段随机命中敌方 | 系统按 `hit_count` 随机采样，允许重复 |
| `ally_single` | 单个友方成员 | 调用方指定，列表长度 = 1 |
| `ally_all` | 全体友方成员 | 系统自动填所有友方成员 |
| `self_only` | 仅出牌者自身 | 系统自动填出牌者名称 |

**"宽进严出"验证策略**：

`DrawCardsActionSystem` 生成的 `CardEntry` 将 LLM 的裸字符串原样保留；消费方在将其转换为 `CardTargetType` 枚举时，若字符串不匹配任何已知值，则直接丢弃该卡并记录 agent warning，不抛出异常。这保证 LLM 的自由输出不会崩溃后续管线，同时在管线边界处维持严格的类型约束。

**随机多段命中（`enemy_random_multi`）的设计要点**：

随机性由 Python 在出牌阶段提前决定，而非委托给仲裁 LLM。这保证目标分配可重现、可日志记录，避免 LLM 在仲裁阶段产生幻觉目标。`PlayCardsAction.targets` 中可包含重复的敌人名称（例如三段命中中有两段落在同一个敌人身上），仲裁系统以 `dict.fromkeys` 去重后构建伤害统计字典，再按该目标在 `targets` 列表中出现的次数累加伤害，最终生成每个独立目标的结算结果。

`ALLY_*` 系列枚举值已定义但暂为占位：当前版本不存在以友方为目标的伤害结算路径，`ally_single` / `ally_all` 目前仅用于治疗类或增益类卡牌的语义标注。

---

### ArbitrationActionSystem（步骤 10）

**源码**：`src/ai_rpg/systems/arbitration_action_system.py`  
**监听**：`PlayCardsAction`

这是战斗的数值结算核心。每次单张出牌后立即触发（`ActionCleanupSystem` 保证每帧只有一个角色出牌）。

**流程**：

1. 从 `PlayCardsAction` 提取卡牌信息（伤害 / 格挡 / 目标类型）
2. 读取出牌者与目标当前 HP / 格挡，以及 `ARBITRATION` 相位的状态效果，构建仲裁 Prompt
3. 调用 LLM 计算最终伤害，生成战斗日志与演出叙事（`ArbitrationResponse`）
4. 遍历 `final_stats` 更新所有受影响角色的 HP / 格挡
5. 若 `final_stats` 中包含 `status_effect_patches`，原地回写对应状态效果的 `description`（用于更新 `cur` 等动态变量，如"前 N 次被攻击伤害变为 1"的剩余次数）
6. HP 归零的角色添加 `DeathComponent`

**Prompt 压缩**（`use_compressed_prompt`，默认开启）：对话历史（写入 `stage_entity` context）只写入每次出牌变化的动态感知部分（回合号、出牌者 HP/格挡、卡牌字段、目标 HP/格挡、仲裁状态效果），静态的计算规则与输出格式说明以 `combat_arbitration_full_prompt` 附挂在消息额外字段中保留，LLM 推理仍使用全量版。此外，ENEMY_RANDOM_MULTI 卡牌的 `hit_assignment`（系统预先随机确定的命中分配列表）属于动态内容，保留在压缩版中；`rm.rules`（静态规则说明）和 `rm.log_example`（静态格式示例）仅保留在全量版。

**状态效果动态变量机制**：

`StatusEffect.description` 同时承担规则说明与动态状态存储，例如：`"被攻击前3次伤害变为1，cur=2/max=3"`。  
仲裁 LLM 读取 `cur` 后应用规则，并通过 `status_effect_patches` 将消耗后的新 `description`（含更新的 `cur`）写回组件。  
`cur` 与 `duration` 两套机制独立并行：`duration` 由 `CombatRoundCleanupSystem` 按回合递减，`cur` 由仲裁 LLM 按命中次数递减。

---

### PostArbitrationActionSystem（步骤 12）

**源码**：`src/ai_rpg/systems/post_arbitration_action_system.py`  
**监听**：`PostArbitrationAction`（`ADDED`）

`ArbitrationActionSystem` 结算成功后，若 `ArbitrationResponse.trigger_post_arbitration == True`，会向 stage entity 添加 `PostArbitrationAction`，触发本系统。`filter()` 接受两类实体（Stage OR Actor），`react()` 内部按顺序处理两个批次：

**批次一：Stage 路径**（当前唯一激活路径）

- 实体条件：具有 `StageComponent + DungeonComponent`
- combat stage 的 LLM agent 以"地牢主视角"对场内存活角色决定是否：
  - 追加状态效果（`add_effects`）
  - 向角色手牌塞入特殊卡牌（`inject_cards`）
- 若上下文中无可利用的环境要素，LLM 必须输出空 `per_actor` 数组（不干预）
- 塞牌位置由 `CardInjectStrategy` 控制：`APPEND`（尾部追加）或 `RANDOM_INSERT`（随机插入）
- 实现方法：`_process_stage`

**批次二：Actor 路径**（暂为 stub）

- 实体条件：具有 `ActorComponent`
- 触发点尚未在 `ArbitrationActionSystem` 中实现（actor entity 未被添加 `PostArbitrationAction`），当前此批次永远为空
- 当 `_process_actor` 被调用时仅打 debug 日志，无 LLM 推理
- 未来设计方向：actor 自身的 LLM agent 决定仲裁后的角色级反应，配套在 `ArbitrationResponse` 中添加独立控制字段 `trigger_actor_reflection`

**前置守卫**：战斗状态须为 `ONGOING`，否则整批跳过。

**Prompt 压缩**（`use_compressed_prompt`，默认开启）：对话历史只写入动态感知部分（回合编号、出牌者说明、存活角色 HP/格挡/状态效果），静态规则与 JSON 示例以 `stage_post_arbitration_full_prompt` 附挂。

---

### CombatRoundCompletionSystem（步骤 13）

**源码**：`src/ai_rpg/systems/combat_round_completion_system.py`  
**类型**：`ExecuteProcessor`

**触发条件**：战斗进行中，最新回合存在且尚未完成，且回合快照（`actor_order_snapshots`）非空。

判断依据：遍历本场景所有存活角色，若全部角色的 `RoundStatsComponent.energy <= 0`（或无该组件），则将 `Round.is_completed` 置为 `True`。

设计要点：
- 基于 **energy** 判断，反映运行时真实剩余行动数，比结构性计数更准确
- 位于 `PostArbitrationActionSystem` 之后，所有 energy 消耗已结算
- 位于 `CombatOutcomeSystem` 之前，使胜负检查能感知到回合完成状态

---

### CombatRoundTransitionSystem（步骤 16）

**源码**：`src/ai_rpg/systems/combat_round_transition_system.py`  
**策略**：`ActionOrderStrategy.SPEED_ORDER`（按速度属性降序排列行动顺序）

位于管线末端，负责在两种情况下创建新回合：

1. **战斗首帧**（`current_rounds == 0`）：`CombatInitializationSystem` 将战斗状态切换为 `ONGOING` 后，本系统在同一帧末端创建 Round 1，直接跳过"上一回合是否完成"的检查。
2. **常规轮转**（`current_rounds > 0` 且上一回合 `is_completed == True`）：旧回合由 `CombatRoundCleanupSystem` 清理后，本系统创建新回合。

创建新回合时，按配置策略对当前存活角色排序，将结果写入 `Round.actor_order_snapshots`（快照列表），并初始化 `Round.current_actor_name` 为第一个行动者。

可选策略：`RANDOM`（随机打乱）/ `CREATION_ORDER`（按实体创建顺序）/ `SPEED_ORDER`（速度降序）

参见 [[design-patterns#3. 状态守卫（State Guard）]]

---

### CombatArchiveSystem（步骤 16）

**源码**：`src/ai_rpg/systems/combat_archive_system.py`  
**类型**：`ExecuteProcessor`（含状态守卫）

**触发条件**：`CombatArchiveEvent` 存在（由 `CombatOutcomeSystem` 在战斗结束时写入）。

执行内容：

1. 调用 LLM 为每个参战角色生成第一人称战斗回忆录（≤150字）
2. 压缩角色消息历史，去除冗余中间状态
3. 将战斗经历写入角色的长期记忆存储（向量数据库）

参见 [[design-patterns#3. 状态守卫（State Guard）]]
