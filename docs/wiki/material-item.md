# 材料系统（MaterialItem）

---

## 定位

`MaterialItem` 是**不可直接使用**的原料类道具：不参与战斗、不携带任何属性词缀，唯一设计用途是在家园工坊中被消耗，经由 LLM 推理合成为 `ConsumableItem`、`GearItem` 或 `CostumeItem` 三者之一（合成发起时即确定产物类型，分别对应不同的合成流程）。

这种设计将材料与合成产物的「生产-消费」关系清晰分离：材料是工坊的唯一原料入口，合成是其唯一出口。

---

## 与工坊系统的交互

工坊合成由三个世界实体作为 LLM agent：消耗品由「世界.消耗品工坊」（`ConsumableWorkshopComponent`）驱动，装备由「世界.装备工坊」（`GearWorkshopComponent`）驱动，时装由「世界.时装工坊」（`CostumeWorkshopComponent`）驱动。三类产物共用同一材料池，仅合成提示词与产物 schema 因目标类型而异；各工坊的审美与内容约束由其蓝图 `role_rules` 注入。材料的名称与描述文本是 LLM 推断合成结果的**唯一语义线索**——材料描述越具体，合成出的产物越具个性化。这也解释了为何材料与各类合成产物均采用带前缀的命名约定（`材料.XXX` / `消耗品.XXX` / `装备.XXX` / `时装.XXX`）以维持语义清晰度。

合成完成后，所用材料从储物箱（`StorageComponent`）中扣减（count 递减、归零移除），合成产物取而代之进入储物箱；产物携带 `resources` 记录本次消耗的原料清单，作为来源可追溯凭证。

→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)（合成产物的使用效果提示词与战斗使用管道）
→ 参见：[装备系统（GearItem）](gear-item.md)（合成产物的卡牌规格与装备物化管道）
