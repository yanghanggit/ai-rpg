# 仲裁后场景干预系统（PostArbitrationActionSystem）

战斗不只发生在角色之间，也发生在角色与场景之间。`PostArbitrationActionSystem` 的设计意图是：在任意一次仲裁完成后，让**场景实体**根据当前叙事上下文，将环境要素转化为对角色的即时物理干预——向手牌中塞入可借用的场景物件牌，或向角色追加环境引发的状态效果。

这一设计将"战场叙事"与"战斗数值"绑定：LLM 生成的战斗描述不只是文本装饰，它真实地影响后续出牌选项和角色状态。

---

## 场景实体作为推理主体

场景实体与角色实体一样，拥有独立的 LLM 上下文（system message + 对话历史）。System message 由初始化阶段写入，描述该场景的物理环境（地形、气候、可交互物件等）；后续每一回合的战斗叙事以对话历史的形式持续累积。

`PostArbitrationActionSystem` 利用这一完整上下文，要求 LLM 推断：哪些环境要素在当前叙事中已经被触发或描述，是否仍处于可交互状态，以及它们对场内角色会产生何种物理后果。LLM 的身份由 system message 锚定（"你扮演场景"），因此每次 prompt 只需提供本回合的动态感知内容（当前角色状态、行动角色名称），不必重复声明场景身份。

干预必须有叙事依据：LLM 只能将**上下文中已描述过的**环境要素转化为效果或卡牌，不得凭空引入场景中从未出现的物件，也不得引入角色内在情绪（恐惧、勇气等非物理来源）。

---

## 外来牌的生命周期

注入手牌的场景物件牌属于**外来牌**，其来源标记为场景实体，而非持牌角色。这一来源标记决定了它的整个生命周期：

- **本回合打出**：外来牌经由正常出牌路由进入弃牌堆，但不会参与后续 DrawPile 的抽牌循环——它是一次性机遇，不是永久获得的牌。
- **回合末未出**：外来牌被直接丢弃，不归入弃牌堆。

这一机制确保了语义一致性：场景中的断柱只属于当下这一刻，用不掉就消失，不会在后续回合中神秘复现。

同一手牌内不会重复塞入同名牌；同名状态效果也不会重复追加，防止叠加失控。

→ 参见：[地下城生成流程（Dungeon Generation Pipeline）](dungeon-generation.md)

---

## 触发来源

`PostArbitrationActionSystem` 被设计为**通用仲裁后钩子**，而非出牌专属。任何一次仲裁结算若判定该行动影响了场景，均可触发本系统。当前有三个仲裁系统可以发出触发信号：

- `PlayCardsArbitrationSystem`：出牌仲裁结算后
- `UseConsumableItemArbitrationSystem`：消耗品使用仲裁结算后
- `UseGearItemArbitrationSystem`：装备使用仲裁结算后

→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)  
→ 参见：[装备系统（GearItem）](gear-item.md)

---

## 与其他系统的关系

`PostArbitrationActionSystem` 只在战斗进行中生效，只关联地下城场景实体，不修改角色的持久牌库（`DeckComponent`），也不触及跨战斗的任何状态。战斗结束后，`CombatPileTeardownSystem` 清理所有战斗子堆，外来牌的残留也随之消除。

回合状态清理（`clear_round_state`）负责在每回合末将未打出的外来牌从手牌中过滤丢弃，`HandComponent` 随后被移除，为下一回合的抽牌做准备。

→ 参见：[地下城生成流程（Dungeon Generation Pipeline）](dungeon-generation.md)
