# 消耗品系统（ConsumableItem）

---

## 定位

消耗品是战斗中可主动使用的**队伍级**道具，库存统一由 player 持有（团队背包），使用动作挂在「当前行动的我方角色」上——谁轮到自己回合，谁发起使用。

使用**不消耗 energy、不推进回合**：消耗品本身固定 **0 费**，且使用时只是把内置卡牌**物化为手牌**；真正结算效果的是之后打出的那张牌。是否轮到下一角色完全由过牌（pass turn）决定。

消耗品与装备（`GearItem`）**同构**：合成时固化内置卡牌（`cards`），战斗中物化为手牌、走普通出牌逻辑。区别只有两点：

- **一次性**：消耗品卡固定 `exhaust=True`，打出后进 `ExhaustPile`，不像装备那样在战斗结束时归还；
- **用后即扣**：物化时立刻从队伍背包扣减 1 份库存，装备则是「用后归还」。

→ 参见：[装备系统（GearItem）](gear-item.md)（同为队伍级道具，物化为手牌）

---

## 内置卡牌（cards）

`ConsumableItem` 携带 `cards: List[Card]`，与 `GearItem.cards` 同名同语义——它是**一份**消耗品携带的内置牌（一般仅一张，与 gear 同构）：

- 合成/蓝图阶段即固化为完整 `Card` 规格，战斗使用不再调用 LLM；
- 卡牌固定 **`cost=0`** 且 **`exhaust=True`**，由 `ConsumableItem` 的模型校验**强制**（任何入口写入不合规的卡都会构造失败）；
- 本阶段消耗品**只做伤害**：效果直接由 `Card.damage`（配 `hit_count` / `target_type`）承载，不走治疗、格挡或状态。

物化数量 = **每个内置牌 × `count`**：一次使用会消耗整条库存（其全部 `count`），每张内置牌各生成 `count` 份手牌副本。

---

## 战斗使用管道

消耗品使用经过两个串联阶段：

**物化阶段**（`UseConsumableItemActionSystem`）：先从团队背包（player 的 `InventoryComponent`）**按 uuid 移除整条消耗品**（消耗其全部 `count`）；扣库存成功后才把 `cards` 物化为手牌——**每个内置牌 × count** 生成对应份数的独立副本（重生成 `uuid`、`source` 记为发起行动者、强制 `retain=True`）。随后向场景内所有存活角色广播使用通知，并写入本回合的 `consumable_log` / `consumable_narrative` / `consumable_use_count`（与装备的 `gear_*` 字段对称）。若背包中找不到该条消耗品，则**不物化、不广播**。

**结算阶段**（`PlayCardsArbitrationSystem`）：物化出的牌与任何普通手牌一样，由出牌仲裁结算伤害，结果写入 `cards_log` / `cards_narrative`。

> 为什么物化出的牌要强制 `retain=True`：回合末 `clear_round_state` 会把非 retain 手牌塞进弃牌堆，而 DrawPile 耗尽时弃牌堆会被洗回 DrawPile。若不 retain，一张本回合没用掉的消耗品卡会在后续回合被重新抽到并再次打出，而库存早已扣了 1 份——等于一份消耗品重复生效。`retain` 让它在手牌中留到打出为止，战斗结束由 `CombatPileTeardownSystem` 清掉副本。
>
> 消耗品卡**不叠加角色属性**：`Card.damage` 就是最终伤害（与装备刻意不同——装备物化时会叠加持有者的 `attack` / `defense`）。

---

## 合成来源

消耗品可由「世界.消耗品工坊」从储物箱材料合成，命名遵循「消耗品.XXXX」约定。合成走 `agent_loop` 工具调用模式（与装备工坊一致：`list_consumable_examples` → `get_consumable_example` → `submit_consumable` → `finish_consumable`），由 LLM 依材料推断名称、描述与一张伤害卡规格；提交时强制 0 费、一次性、纯伤害。

合成产出入库时按堆叠身份合并：仅当与库存中既有条目「同名且内置卡牌规格一致」时并入该堆叠、数量累加，否则作为新条目追加。堆叠身份取卡牌的机械字段（`damage` / `hit_count` / `block` / `cost` / `target_type` / 词缀等，**不含 `uuid` / `source` / 叙事文本**）。初始播种也可直接写入多于一件的堆叠。

→ 参见：[材料系统（MaterialItem）](material-item.md)（合成管道与材料消耗规则）
→ 参见：[工坊合成管道（Craft Pipeline）](craft-pipeline.md)
