# 装备系统（GearItem）

---

## 定位

装备是战斗中可主动使用的**持久性**道具。使用后从背包移动到目标角色的 `EquippedGearComponent`，持续提供属性加成直至关卡结束。每个角色只有一个装备槽，后挂载者覆盖前者（旧装备当前版本不自动归还）。

---

## 与消耗品的关键差异

| 维度 | ConsumableItem | GearItem |
| ------ | --------------- | ---------- |
| 使用后道具去向 | count 扣减，耗尽移除 | 从背包移至 `EquippedGearComponent` |
| 属性变化来源 | LLM 仲裁推断 HP delta | `stat_bonuses` 确定性叠加，系统直接计算 |
| 仲裁职责 | HP 变化 + 叙事 + 可触发 `PostArbitrationAction` | **纯叙事广播**，不做 HP 计算，不解析 JSON |
| `modifiers` 字段 | 注入本次仲裁 prompt | 字段存在，当前仲裁不消费（保留扩展） |

`affixes` 字段两者语义相同：触发延迟 `AddStatusEffectsAction` 推理。

→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)（affixes / modifiers 分离的设计决策来源）

---

## count 不变量

`GearItem.count` 必须为 1。装备不可堆叠，系统在从背包移除时以 `assert` 强制检查，违反则抛出异常而非静默处理。

---

## EquippedGearComponent 生命周期

| 时机 | 操作 |
| ------ | ------ |
| 战斗中使用装备 | 装备从 `InventoryComponent` pop，`replace` 挂载到目标 |
| 目标已有装备时再次装备 | 旧装备被覆盖丢失（当前不归还） |
| 进入下一关 / 退出地下城 | `clear_between_stages` → `clear_equipped_gear`：所有装备归还玩家背包，组件移除 |

`clear_between_stages` 同时清除手牌（`RoundStatsComponent`）与状态效果（`StatusEffectsComponent`），装备归还是其中一步。

---

## 系统边界

- 装备使用不消耗 energy，与消耗品使用性质相同。
- `target_type` 支持 `ALLY_SINGLE`；`CARD` 暂不支持。

→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)
