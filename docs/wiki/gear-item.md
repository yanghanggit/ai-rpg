# 装备系统（GearItem）

---

## 定位

装备是战斗中可主动使用的**持久性**道具，只能由 `InventoryComponent` 持有者（player）在本人行动回合发动，目标固定为单一友方单位（可选择 player 自身），不携带 `target_type` 字段，卡牌目标尚未支持。使用消耗被装备目标本回合 `GearItem.cost` 点 `energy`，不足则服务层拒绝；装备动作不调用回合推进逻辑，是否轮到下一角色完全由过牌（pass turn）决定。

`stat_bonuses` 由前置系统确定性写入 `EquippedGearComponent`，不经 LLM；仲裁系统则由 LLM 评估即时修正词缀（`modifiers`）对目标 HP 的叠加影响，结果写入本回合战斗日志并广播全场。

---

## EquippedGearComponent 生命周期

装备生效采用**移动语义**：物品对象直接从背包持有者的 `InventoryComponent` 移出、挂载为目标角色的 `EquippedGearComponent`（对象引用转移，非深拷贝），以关卡为生命周期单元，从不重新生成或凭空消失。

- **换装**：同一目标再次装备时，新装备替换旧装备，被覆盖的旧装备归还背包持有者。
- **清关/退出**：所有 `EquippedGearComponent` 被清空，装备对象统一归还 player 的 `InventoryComponent`。

---

## 词缀机制

装备携带三类词缀，各自绑定不同触发时机：

- **装备时延迟词缀**：装备生效瞬间由使用装备的仲裁系统评估，作用于装备者自身（如护甲的承击韧性）。
- **命中时延迟词缀**：出牌命中目标后由出牌仲裁系统评估，作用于被命中目标（如武器的流血、撕裂）。
- **即时修正词缀**：由装备/出牌/消耗品三类仲裁系统注入提示词，对 LLM 当轮数值计算产生即时修正；设计规范与卡牌一致。

→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)（两类词缀分离的设计决策来源）

---

## 合成来源

装备也可由工坊系统从材料合成，命名遵循「装备.XXXX」约定；LLM 推理同时生成 `stat_bonuses` 与两类延迟词缀，合成品与非合成装备的加成计算方式完全一致。

→ 参见：[材料系统（MaterialItem）](material-item.md)（合成管道与材料消耗规则）
