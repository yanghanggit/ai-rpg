# 装备系统（GearItem）

---

## 定位

装备是战斗中可主动使用的**持久性**道具。使用后以深拷贝写入目标角色的 `EquippedGearComponent`，持续提供属性加成直至关卡结束；原物品始终留在背包（`InventoryComponent`），不被移除。

每次装备消耗一点耐久（`durability -= 1`）；耐久归零或装备正在被某角色激活时，均无法再次装备。进入地下城或离开地下城返回家园时，所有背包装备的耐久恢复至 `max_durability`。

---

## 与消耗品的关键差异

| 维度 | ConsumableItem | GearItem |
| ------ | --------------- | ---------- |
| 使用后道具去向 | `count` 扣减，耗尽移除 | 深拷贝写入 `EquippedGearComponent`，原件保留背包 |
| 属性变化来源 | LLM 仲裁推断 HP delta | `stat_bonuses` 确定性叠加，系统直接计算 |
| 仲裁职责 | HP 变化 + 叙事 + 可触发 `PostArbitrationAction` | **纯叙事广播**，不做 HP 计算，不解析 JSON |
| 使用限制 | 无次数限制（受 `count` 约束） | 耐久归零或已激活则拒绝；每关卡重置耐久 |
| `modifiers` 字段 | 注入本次仲裁 prompt | 字段存在，当前仲裁不消费（保留扩展） |

`affixes` 字段两者语义相同：触发延迟 `AddStatusEffectsAction` 推理。

→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)（affixes / modifiers 分离的设计决策来源）

---

## 耐久机制

`max_durability`（默认 3）为上限，`durability` 为当前值，初始与上限相等。

- **装备时**：`UseGearItemActionSystem` 从 `InventoryComponent` 按 `uuid` 找到原件，执行 `durability -= 1`。
- **拦截条件**（服务层 `activate_use_gear`）：`durability <= 0` 或该装备的 `uuid` 已存在于某实体的 `EquippedGearComponent`。
- **恢复时机**：`enter_dungeon_first_stage` 调用 `_enter_dungeon_stage` 前，以及 `exit_dungeon_and_return_home` 执行 `clear_between_stages` 后，均调用 `_restore_gear_durability` 将所有背包 `GearItem` 的 `durability` 重置为 `max_durability`。

同一场 Combat 内，因"已激活"拦截，同一装备事实上只能消耗一次耐久。

---

## EquippedGearComponent 生命周期

| 时机 | 操作 |
| ------ | ------ |
| 战斗中使用装备 | 深拷贝写入目标 `EquippedGearComponent`；`durability -= 1` |
| 装备已被激活或耐久归零 | 服务层拒绝，不创建 Action |
| 目标已装备其他物品时再次装备 | `replace` 覆盖；被覆盖物品保留背包 |
| 进入下一关 / 退出地下城 | `clear_between_stages` 移除所有 `EquippedGearComponent`；随后 `_restore_gear_durability` 恢复耐久 |

---

## 系统边界

- 装备使用不消耗 energy，与消耗品使用性质相同。
- `target_type` 支持 `ALLY_SINGLE`；`CARD` 暂不支持。

→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)
