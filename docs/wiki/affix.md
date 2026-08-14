# 词缀（Affix）

---

## 定位

affix 是 `StatusEffect` 的种子与触发源——一条延迟信号，先由设计者产出，再经计算端搬运，最终由目标角色推理落地为状态效果。它横跨卡牌、装备、消耗品、场景四类来源，但共享同一条"创建 → 流转 → 使用"的单向管道：设计者只写种子，代码只搬运，LLM 只落地。全管道唯一的 LLM 出口是 `AddStatusEffectsActionSystem`。

---

## 创建：设计者产出种子

affix 只能由设计者产出，运行时仲裁者不得现编。两类设计者：

**静态设计**——`Card`、`GearItem`、`ConsumableItem` 上固化的词缀。来源有二：策划在 demo 预写，或 LLM 在生成阶段（牌库生成、工坊打造）创作后固化。固化后运行时只读。

**动态设计**——仅战斗初始化一处，场景实体 LLM 扮演策划，依据场景叙事现编场景词缀。它属于设计角色而非仲裁角色，产物与静态词缀走同一条下游管道。

关键边界：三个仲裁阶段（出牌 / 消耗品 / 装备结算）的 LLM 只做确定性结算，不设计 affix，仲裁响应不携带任何词缀字段。设计与仲裁的分离，是"机制与内容分离"在运行时的一次重申。

→ 参见：[LLM 生成型游戏对象：Card 与 StatusEffect](llm-generated-objects.md)

---

## 流转：计算端搬运

设计者产出的种子由代码统一包装为 `AffixTrigger`，累积为 `AddStatusEffectsAction`，挂到受影响角色实体上。此环节不含 LLM——无论种子来自静态字段还是场景设计，搬运路径一致，只做读取、打包、挂载。

挂载边界由出牌目标这一确定性数据决定，而非 LLM 结算结果：出牌场景下词缀只落到实际目标，不会扩散到场内无关角色。这是计算端不依赖 LLM 输出划定影响范围的体现。

---

## 使用：唯一 LLM 落地

`AddStatusEffectsActionSystem` 是全管道唯一的 LLM 出口。每条 `AffixTrigger` 严格一对一落地为一个 `StatusEffect`，由受影响角色自身推理——同一根毒刺扎在不同角色身上，落地形态由目标体质决定。落地时回填两个溯源要素：种子原文（`affix`）与创造者（`source`）。

→ 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)

---

## 回述：种子留痕

`StatusEffect` 保存种子原文与创造者，是调试与迭代的抓手。调试时拿种子文本去对应设计者的对话历史反查，即可定位产出它的提示词；迭代时据此修改设计提示词，观察下一批种子的变化。动态设计的种子同样值得留痕——调试对象恰恰是产出动态内容的提示词。

---

## 跨系统关系

- 卡牌、装备、消耗品的词缀由各自的生成与合成管道产出 → 参见：[装备系统（GearItem）](gear-item.md)、[消耗品系统（ConsumableItem）](consumable-item.md)、[工坊合成管道（Craft Pipeline）](craft-pipeline.md)
- 场景词缀由战斗初始化的场景设计产出 → 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)
- affix 的落地目标与 `StatusEffect` 的生成点 → 参见：[LLM 生成型游戏对象：Card 与 StatusEffect](llm-generated-objects.md)
