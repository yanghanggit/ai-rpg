# 场景塞牌系统（InjectCardsActionSystem）

战斗不只发生在角色之间，也发生在角色与场景之间。`InjectCardsActionSystem` 的设计意图是：在任意一次出牌/使用消耗品/使用装备的仲裁完成后，让**场景实体**回顾自己刚记录下的当回合叙事上下文，判断是否需要将环境要素转化为对角色的即时物理干预——向手牌中塞入可借用的场景物件牌。

这一设计将"战场叙事"与"战斗数值"绑定：LLM 生成的战斗描述不只是文本装饰，它真实地影响后续出牌选项。

---

## 场景实体作为推理主体

场景实体与角色实体一样，拥有独立的 LLM 上下文（system message + 对话历史）。System message 由初始化阶段写入，描述该场景的物理环境（地形、气候、可交互物件等）；后续每一回合的战斗叙事以对话历史的形式持续累积。

关键机制：`InjectCardsActionSystem` 不接收任何显式的"触发依据"字段——它直接与 `PlayCardsAction`/`UseConsumableItemAction`/`UseGearItemAction` 的 ADDED 事件绑定，在同一帧内紧跟在对应的仲裁系统之后执行。当它运行时，仲裁系统已经把本次行动的 combat_log/narrative 以 human/ai message 写入了场景实体共享的对话上下文中。`InjectCardsActionSystem` 复用同一个 `context` 对象发起新的 prompt，要求 LLM 回顾刚才那段叙事推断：哪些环境要素在当前叙事中已经被触发或描述，是否仍处于可交互状态，以及它们对场内角色会产生何种物理后果。LLM 的身份由 system message 锚定（"你扮演场景"），因此每次 prompt 只需提供本回合的动态感知内容（当前角色状态），不必重复声明场景身份。

干预必须有叙事依据：LLM 只能将**上下文中已描述过的**环境要素转化为效果或卡牌，不得凭空引入场景中从未出现的物件，也不得引入角色内在情绪（恐惧、勇气等非物理来源）。

---

## 外来牌的生命周期

注入手牌的场景物件牌属于**外来牌**，其来源标记为场景实体，而非持牌角色。这一来源标记决定了它的整个生命周期：

- **本回合打出**：外来牌经由正常出牌路由进入弃牌堆，但不会参与后续 DrawPile 的抽牌循环——它是一次性机遇，不是永久获得的牌。
- **回合末未出**：外来牌被直接丢弃，不归入弃牌堆。

这一机制确保了语义一致性：场景中的断柱只属于当下这一刻，用不掉就消失，不会在后续回合中神秘复现。

同一手牌内不会重复塞入同名牌（同名牌已存在于当前弃牌堆时直接放弃本次塞入）。

→ 参见：[地下城生成流程（Dungeon Generation Pipeline）](dungeon-generation.md)

---

## 触发来源

`InjectCardsActionSystem` 直接监听 3 种行动组件的 ADDED 事件（多 `Matcher` 的 `get_trigger()`），而非依赖任何中间产物组件：

- `PlayCardsAction`（出牌）
- `UseConsumableItemAction`（使用消耗品）
- `UseGearItemAction`（使用装备）

因为这三种行动都发生在角色实体上，`InjectCardsActionSystem` 每次通过 `resolve_stage_entity(actor_entity)` 解析出对应的场景实体，与 `PlayCardsArbitrationSystem`/`UseGearItemArbitrationSystem`/`UseConsumableItemArbitrationSystem` 解析场景的方式一致。

注意：与之前版本不同，现在**每次**出牌/使用消耗品/使用装备都会触发一次 LLM 评估，不再依赖仲裁系统预先判断是否"值得考虑场景干预"。是否实际塞牌完全交由 `InjectCardsActionSystem` 自己的 LLM 调用判断。

→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)  
→ 参见：[装备系统（GearItem）](gear-item.md)

---

## 流水线位置与执行顺序依赖

`InjectCardsActionSystem` 在处理流水线（`dbg_game_process_pipeline.py`）中注册在 `PlayCardsArbitrationSystem` / `UseConsumableItemArbitrationSystem` / `UseGearItemArbitrationSystem` / `AddStatusEffectsActionSystem` 之后。这个顺序不能调换：只有先让仲裁系统完成 `add_human_message`/`add_ai_message` 写入场景对话历史，`InjectCardsActionSystem` 才能在同一帧内复用到含有本次叙事的最新上下文。

---

## 与其他系统的关系

`InjectCardsActionSystem` 只在战斗进行中生效，不修改角色的持久牌库（`DeckComponent`），也不触及跨战斗的任何状态。战斗结束后，`CombatPileTeardownSystem` 清理所有战斗子堆，外来牌的残留也随之消除。

回合状态清理（`clear_round_state`）负责在每回合末将未打出的外来牌从手牌中过滤丢弃，`HandComponent` 随后被移除，为下一回合的抽牌做准备。

→ 参见：[地下城生成流程（Dungeon Generation Pipeline）](dungeon-generation.md)
