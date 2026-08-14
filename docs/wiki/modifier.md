# 即时修正词缀（modifier）

---

## 定位

modifier 是"词缀二分"中的即时分支——一次性数值修正，仅作用于本次仲裁结算，不产生持续状态。它与 affix 互为镜像：modifier 即时且携带数值，由仲裁 LLM 消费；affix 延迟且仅作信号，由落地 LLM 消费。二者共享"设计者写词缀、代码搬运、LLM 消费"的同一范式，只是消费阶段不同。

→ 参见：[词缀（Affix）](affix.md)

---

## 创建：设计者固化

modifier 由设计者写入 `Card`、`GearItem`、`ConsumableItem`——策划在 demo 预写，或 LLM 在生成阶段（牌库生成、工坊打造）创作后固化。固化后运行时只读，与 affix 同源。

---

## 使用：注入仲裁结算

出牌 / 使用消耗品 / 使用装备时，代码读取 modifier 并注入仲裁提示词，由仲裁 LLM 将修正规则叠加到确定性结算之上，体现为本次结算后的血量变化。它不经过 `AffixTrigger`，不落地 `StatusEffect`，生命周期止于本次仲裁。

→ 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)

---

## 边界

modifier 只允许"本次仲裁内立即生效"的表述，严禁"本回合"、"下回合"、"持续 N 回合"等跨回合内容——此类持续性效果一律归入 affix。这一时效二分是任何词缀落笔前必须先判定的前提。

→ 参见：[词缀（Affix）](affix.md)

---

## 跨系统关系

- 消费方为三个仲裁系统（出牌 / 消耗品 / 装备结算）→ 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)
- 产出方为牌库生成与工坊合成 → 参见：[工坊合成管道（Craft Pipeline）](craft-pipeline.md)、[LLM 生成型游戏对象：Card 与 StatusEffect](llm-generated-objects.md)
