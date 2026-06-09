# 消耗品系统（ConsumableItem）

---

## 定位

消耗品是战斗中可主动使用的一次性道具。使用**不消耗 energy**，可在己方行动阶段内任意次数触发；每次使用均驱动一次独立 LLM 仲裁，仲裁结果写回 HP 并广播叙事。

---

## 词缀机制设计

`ConsumableItem` 有两类词缀字段，生效时机不同，因此必须分开：

- `affixes`（延迟词缀）：格式 `[名称]:触发倾向描述`。仲裁结束后触发独立 `AddStatusEffectsAction` 推理，由 LLM 决定是否生成持续 `StatusEffect`。
- `modifiers`（即时修正词缀）：格式 `[名称]:即时修正描述`。直接注入本次仲裁 prompt，LLM 在计算本回合 HP 变化时须将其纳入。

早期曾用 `!` 前缀区分即时修正，已废弃，改为字段分离。

→ 参见：[装备系统（GearItem）](gear-item.md)（采用相同字段设计，但仲裁系统当前不消费 `modifiers`）

---

## 合成来源

消耗品可通过工坊（`CraftConsumableActionSystem`）由材料合成。LLM 推断合成结果并同步填充 `affixes` 与 `modifiers`，使合成品具备个性化能力。

---

## 系统边界

- 消耗品使用不影响 `EquippedGearComponent`，不触发装备仲裁。
- `target_type = CARD` 暂不支持，服务层会拒绝此调用。

→ 参见：[装备系统（GearItem）](gear-item.md)
