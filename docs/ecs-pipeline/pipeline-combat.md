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
| 4 | `CombatInitializationSystem` | Execute | 初始化战斗：注入战场上下文，创建第一回合 |
| 5 | `DrawCardsActionSystem` | Reactive | 为角色生成手牌（历史牌组 + LLM 新牌） |
| 6 | `EnemyPlayDecisionSystem` | Execute | 敌方 AI 决策出哪张牌 |
| 7 | `PlayActionNarrationSystem` | Execute | LLM 润色出牌叙事 |
| 8 | `PlayCardsActionSystem` | Reactive | 执行出牌，触发后续仲裁链 |
| 9 | `RetreatActionSystem` | Reactive | 处理撤退行动 |
| 10 | `ArbitrationActionSystem` | Reactive | **核心**：AI 仲裁伤害/格挡/HP 结算 |
| 11 | `AddActorStatusEffectsActionSystem` | Reactive | 为角色追加状态效果（最多 2 个/帧） |
| 12 | `StagePostArbitrationActionSystem` | Reactive | Stage Agent 干预：追加效果或随机塞牌 |
| 13 | `CombatOutcomeSystem` | Execute | 检测胜负：友方/敌方全灭则结算 |
| 14 | `CombatRoundCleanupSystem` | Execute | 清除旧回合手牌与格挡，递减状态效果 |
| 15 | `CombatRoundTransitionSystem` | Execute | 创建新回合，按速度排序生成行动顺序 |
| 16 | `CombatArchiveSystem` | Execute | 战斗归档：LLM 生成总结，压缩消息（状态守卫） |
| 17 | `ActionCleanupSystem` | Execute | 清理所有 Action → [[systems-shared#ActionCleanupSystem]] |
| 18 | `DestroyEntitySystem` | Execute | 销毁标记实体 → [[systems-shared#DestroyEntitySystem]] |
| 19 | `EpilogueSystem` | Execute | flush 状态 → [[systems-shared#EpilogueSystem]] |

---

## 核心系统详解

### CombatInitializationSystem（步骤 4）

**源码**：`src/ai_rpg/systems/combat_initialization_system.py`  
**类型**：`ExecuteProcessor`（含状态守卫）

**触发条件**：当前无回合记录（战斗尚未初始化）。

执行内容（无 LLM 推理，纯上下文注入）：

- 向所有参战角色注入战场情境通知（场景名 / 场景描述 / 其他角色外观与阵营 / 自身属性）
- 以模拟 AIMessage 保证 agent 对话历史连续性
- 创建第一回合，并为所有参战角色添加 `AddStatusEffectsAction`，触发初始状态效果评估

参见 [[design-patterns#3. 状态守卫（State Guard）]]

---

### DrawCardsActionSystem（步骤 5）

**源码**：`src/ai_rpg/systems/draw_cards_action_system.py`  
**监听**：`DrawCardsAction`（`max_num_cards=3`）

**抽牌策略**（历史牌优先 + 保证新鲜度）：

- 从 `DeckComponent`（历史牌组）取最多 `max_num_cards - 1` 张（FIFO 消耗）
- 至少 1 张由 LLM 实时生成，结合角色当前属性（HP/攻击/防御）和状态效果
- 两部分合并为最终手牌写入 `HandComponent`

每张牌包含：`name` / `description` / `damage_dealt` / `block_gain` / `hit_count` / `target_type` / `status_effect_hint`

参见 [[design-patterns#4. 并行 LLM 推理]]

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

**状态效果动态变量机制**：

`StatusEffect.description` 同时承担规则说明与动态状态存储，例如：`"被攻击前3次伤害变为1，cur=2/max=3"`。  
仲裁 LLM 读取 `cur` 后应用规则，并通过 `status_effect_patches` 将消耗后的新 `description`（含更新的 `cur`）写回组件。  
`cur` 与 `duration` 两套机制独立并行：`duration` 由 `CombatRoundCleanupSystem` 按回合递减，`cur` 由仲裁 LLM 按命中次数递减。

---

### CombatRoundTransitionSystem（步骤 15）

**源码**：`src/ai_rpg/systems/combat_round_transition_system.py`  
**策略**：`ActionOrderStrategy.SPEED_ORDER`（按速度属性降序排列行动顺序）

位于管线末端，确保每帧结束时下一回合的行动顺序已就绪，供 `EnemyPlayDecisionSystem` 在下一帧使用。

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
