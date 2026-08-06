# 战斗管道（Combat Pipeline）

---

## 定位

战斗管道是副本模式下驱动整个战斗生命周期的 ECS 处理器链，由 `create_combat_pipeline` 按固定顺序组装。管道以 `pipeline.process()` 为心跳——每轮调用遍历全部系统一次，状态由各实体的组件自然推进，无中心化状态机。

管道承载三类阶段：**仅首次**（战斗初始化）、**循环**（每回合的出牌-仲裁-结算）、**仅末次**（战斗结束后归档与清理）。系统通过组件守卫自行决定是否执行，管道本身不分叉。

---

## 设计决策

### 管道心跳驱动

所有系统共享同一 `process()` 调用周期。一轮心跳中，系统按注册顺序依次执行：先 `DrawCardsActionSystem` 抽牌，再 `MonsterPrePlaySystem` 决策，再到 `PlayCardsArbitrationSystem` 仲裁结算。这种线性编排保证了因果依赖——抽牌一定在决策之前，结算一定在出牌之后。没有事件总线，没有异步消息，管道顺序即因果链。

### 场景实体担任仲裁者

所有战斗仲裁（出牌结算、消耗品使用、装备使用）均由场景实体（stage entity）作为 LLM 仲裁者统一处理。设计意图：场景实体拥有完整的战场上下文（所有角色的对话历史、状态变化通知），能产出一致的叙事。仲裁结果通过 `CombatArbitrationEvent` 广播给场内角色，角色只接收属于自己视角的叙事片段。

→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)（战斗使用管道的双系统结构与本管道仲裁模式一致）

### 两次 LLM 分离决策与结算

出牌分为决策和仲裁两步，由不同系统处理。`MonsterPrePlaySystem` / `PartyPrePlaySystem` 用角色自己的 LLM 上下文做决策（选哪张牌、打谁），产出确定的 `PlayCardsAction`。`PlayCardsArbitrationSystem` 由场景实体做仲裁（伤害多少、触发什么效果），产出 `final_stats` 和叙事文本。分离后决策侧可并行（多个怪物同时想），仲裁侧单线程（保证叙事一致性），且决策不受仲裁 LLM 风格影响。

### 词缀因果链

出牌仲裁可能触发两类后续效果，均在 `PlayCardsArbitrationSystem` 内部串联：

- **延迟词缀**：卡牌的 `affixes` 和装备的 `on_hit_affixes` 不直接改变任何数值，而是生成 `AffixTrigger`，由下游 `AddStatusEffectsActionSystem` 独立推理转为 `StatusEffect`。设计保证 affix 是触发信号而非落地效果。
- **场景交互词缀**：仲裁 LLM 可在 `affixes` 字段输出场景环境引发的效果（如"撞断石柱导致落石"），同样转为 `AddStatusEffectsAction`，与卡牌/装备 affix 在同一 tick 内合并处理。

### 回合行动序列与速度

回合由 `CombatRoundTransitionSystem` 创建，采用 `SPEED_ORDER` 策略——按角色的 `speed` 属性降序排列行动顺序。这意味着高速角色可以先手压制，低速角色后手收割，是角色差异化的重要维度。一个回合完成的标志是所有存活角色均已 pass turn（与 energy 是否耗尽无关：耗尽 energy 的角色无法继续行动，但需要显式 pass 后才标记完成）。

---

## 管道阶段总览

### 第一阶段：战斗初始化（仅首次）

`CombatInitActorSystem` 为每个参战角色挂载空牌堆组件（`DrawPileComponent` / `DiscardPileComponent` / `ExhaustPileComponent`）、注入战场上下文通知（场景叙事 + 对手信息 + 自身属性），并为所有角色添加 `GenerateDeckAction` 触发牌库生成。

`CombatInitStageSystem` 将战斗状态从 `INITIALIZING` 切换为 `ONGOING`，并进行一次场景状态效果判定——LLM 检查场景叙事中是否存在可转化为状态效果的要素（浓烟、灼热地面等），为受影响的角色生成 `[场景]` 词缀，交由 `AddStatusEffectsActionSystem` 落地。战斗规则不在此注入，而是由所有实体的 system message 中预置的 `RPG_SYSTEM_RULES`（含战斗专用规则）统一承载，避免额外的运行时注入复杂度。

`GenerateDeckActionSystem` 为每个角色并行调用 LLM 生成初始牌库。关键词从 `DeckComponent.keywords` 采样，搭配随机骰值决定每张牌的质量档位（失败/正常/优质）。

→ 参见：[卡牌生成 prompt 设计](combat-pipeline.md#卡牌生成与关键词)（关键词-骰值约束机制）

### 第二阶段：回合循环（每回合重复）

**抽牌与调整**：`DrawCardsActionSystem` 从 `DrawPileComponent` 按 FIFO 抽牌写入 `HandComponent`，DrawPile 耗尽时将 `DiscardPileComponent` 洗牌补入。`PostDrawCardsSystem` 检查抽牌角色是否有 DRAW 阶段状态效果，若有则并行调用 LLM 调整手牌数值（如费用增减、伤害惩罚）。

**AI 出牌决策**：`MonsterPrePlaySystem` 和 `PartyPrePlaySystem` 分别处理怪物和 AI 队友的出牌决策。各自读取手牌、对手信息、行动序列，用角色自身 LLM 上下文推理选择卡牌与目标。决策结果为确定的 `PlayCardsAction` 或 `PassTurnAction`。

**动作执行**：`PlayCardsActionSystem` / `UseConsumableItemActionSystem` / `UseGearItemActionSystem` 执行动作的确定性部分（扣 energy、移出背包等），为仲裁做准备。`MoveToDiscardPileSystem` 将已出牌移入弃牌堆，`ExhaustCardsActionSystem` 将标记消耗的牌移入消耗堆。

**仲裁结算**：`PlayCardsArbitrationSystem` 是整个战斗的核心结算节点。由场景实体 LLM 统一仲裁：输入为出牌者属性、卡牌信息、目标属性、状态效果、装备加成，输出为 `final_stats`（各角色新 HP）和叙事文本。仲裁同时处理延迟词缀（`affixes` → `AffixTrigger`）和场景交互词缀的生成。

`UseConsumableItemArbitrationSystem` 和 `UseGearItemArbitrationSystem` 分别结算消耗品和装备使用，结构对称但上下文不同。

`AddStatusEffectsActionSystem` 聚合所有来源的 `AffixTrigger`（卡牌 affix、装备 on_hit_affix、场景交互），并行调用 LLM 为每个受影响角色生成具体的 `StatusEffect`。

`InjectCardsActionSystem` 让场景实体以地牢主视角判断是否需要向场内角色塞入场景卡牌（如环境触发物），实现环境与角色的额外交互维度。

**回合完成与胜负判定**：`CombatRoundCompletionSystem` 检查是否所有存活角色的行动权已结束，若是则标记回合完成。`CombatOutcomeSystem` 检查双方阵营是否全员带有 `DeathComponent`，若是则判定胜负并广播结果。

### 第三阶段：回合末结算（每回合末）

`CombatRoundCleanupSystem` 清除旧回合的手牌状态。`CombatRoundEndEffectSettlementSystem` 并行调用 LLM 为每个有 ROUND_END 阶段状态效果的角色结算 DOT/HOT 扣血/回血，并处理由此产生的死亡。`CombatStatusEffectTickSystem` 推进所有状态效果的 `duration` 计数器（递减或移除到期效果）。

`CombatRoundTransitionSystem` 创建新回合，重置所有角色的 `RoundStatsComponent`（本回合 energy），按 `speed` 降序生成行动顺序，管道进入下一轮心跳。

### 第四阶段：战斗后处理（仅末次）

`CombatLootSystem` 在胜利时为每头死亡怪物调用 LLM 推理掉落材料，写入玩家的 `CombatLootComponent`。`CombatArchiveSystem` 生成战斗总结、压缩消息历史、触发记忆存储，内部有状态守卫确保只在战斗刚结束时执行一次。

`CombatPileTeardownSystem` 将 `DrawPileComponent` / `DiscardPileComponent` / `ExhaustPileComponent` 中的卡牌归还至 `DeckComponent`，恢复战斗前的牌组结构。

---

## 卡牌生成与关键词

每个角色在战斗初始化时通过 `GenerateDeckActionSystem` 生成初始牌库。关键词（存储在 `DeckComponent.keywords`）决定牌的风格走向：

- 关键词由角色设计时写入（如「纯攻击型：不携带任何附加效果」vs「即时破甲型：必须携带一个 modifier」），通过 `_sample_keywords` 按需采样匹配到每张卡牌。
- 每张卡牌附带一个 0–100 的随机骰值，仅当关键词明确说明了骰值用法时生效。典型用法：0-30 为失败（伤害偏低）、31-70 为正常、71-100 为优质（伤害显著高于基础攻击力）。
- 生成 prompt 的 JSON 示例展示空 `modifiers`/`affixes`，格式指引在注释中说明。这避免示例本身误导 LLM 在「纯攻击型」关键词下添加额外效果。

---

## 与其他系统的关系

- **副本生成管道**产出 `CombatRoom`（含 stage + actors + keywords），战斗管道消费它。→ 参见：[副本生成管道（Dungeon Generation Pipeline）](dungeon-generation.md)
- **装备系统**的 `EquippedGearComponent` 提供仲裁阶段的 `modifiers` 和命中时的 `on_hit_affixes`。→ 参见：[装备系统（GearItem）](gear-item.md)
- **消耗品系统**的仲裁走同一场景实体 LLM 模式。→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)
- 战斗结束后，`CombatArchiveSystem` 触发记忆存储，与家园模式的叙事连贯性相关。
- `PlayerActionAuditSystem` 仅在家园管道中生效，战斗管道不引入玩家审核，战斗内玩家出牌由 TUI / CLI 直接指定。
