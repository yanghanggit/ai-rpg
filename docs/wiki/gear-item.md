# 装备系统（GearItem）

---

## 定位

装备是战斗中可主动使用的**持久性**道具，只能由 `InventoryComponent` 持有者（player）在本人行动回合发动。使用时消耗被装备目标本回合 `GearItem.cost` 点 `energy`。使用后以深拷贝写入目标角色的 `EquippedGearComponent`，持续提供属性加成直至关卡结束；原物品始终保留在 `InventoryComponent` 中，不被消耗。

`GearItem` 的基础属性加成（`stat_bonuses`）为确定性计算，由前置系统直接写入 `EquippedGearComponent`，不经 LLM 仲裁。仲裁系统则交由 LLM 评估即时修正词缀（`modifiers`）对目标 HP 的叠加影响，结算结果写入本回合战斗日志并广播至全场。

---

## 能量消耗机制

每次为目标角色装备（含首次装备与替换旧装备）消耗其当前回合 `GearItem.cost` 点 `energy`（`RoundStatsComponent.energy`）；目标剩余 `energy` 小于装备 `cost` 时无法为其装备。

消耗后立即刷新 `Round.current_turn_actor_name`（与出牌/过牌系统一致），确保回合行动顺序状态实时准确；`energy` 随每回合开始按角色属性重新初始化，不需要额外重置逻辑。

---

## EquippedGearComponent 生命周期

`EquippedGearComponent` 以关卡为生命周期单元：

- **写入**：战斗中由 player 本人回合使用装备时，以深拷贝写入单一友方目标角色；已激活或目标 energy 不足则服务层拒绝。
- **覆盖**：对同一目标再次装备时，新装备替换旧装备，被覆盖物品仍留在背包。
- **清除**：进入下一关或退出地下城时，所有角色的 `EquippedGearComponent` 被清空。

---

## 词缀机制

装备携带三类词缀，各自绑定不同的激活上下文。

**装备时延迟词缀**在装备生效的瞬间由使用装备的仲裁系统评估，作用对象为装备者自身；典型用途是护甲类装备的承击韧性或防御激活效果。

**命中时延迟词缀**在持有装备的角色出牌命中目标后，由出牌仲裁系统评估，作用对象为被命中的目标；典型用途是武器类装备的附带状态（如流血、撕裂）。

**即时修正词缀**由三类仲裁系统（装备/出牌/消耗品）注入提示词，对 LLM 当轮数值计算产生即时修正；设计规范与卡牌的即时修正词缀相同。

→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)（两类词缀分离的设计决策来源）

---

## 系统边界

装备目标固定为单一友方单位，可选择 player 自身；装备不再携带 `target_type` 字段。对卡牌目标的支持尚未实现。

→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)
