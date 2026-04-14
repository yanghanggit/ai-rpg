# Archetype 卡牌原型约束系统

> 本文档描述 Archetype 机制的数据模型、ECS 组件设计与在 DrawCardsActionSystem 中的集成方式。  
> 上级入口：[[overview]]

---

## 背景与设计目标

默认情况下，LLM 为每个角色生成手牌时只依赖角色自身的 system message + 战斗上下文，风格完全自由。  
Archetype 机制在此基础上引入**一组自然语言约束规则**，限定 LLM 每次生成卡牌时必须遵循的风格与功能边界。

**典型效果**：

- 无名氏（多段连击型）→ 每张牌的 `hit_count ≥ 2`
- 维拉（状态控制型）→ 每张牌的 `status_effect_hint` 不为空
- 沙狼（纯攻击型）→ `block_gain` 始终为 0，`damage_dealt` 最大化

---

## 数据模型层（entities.py）

`Archetype` 是一个 Pydantic `BaseModel`，只有一个字段 `description`，存储自然语言约束规则。  
`Actor` 模型通过 `archetypes: List[Archetype]` 字段携带约束列表，默认为空列表（即无约束）。

`archetypes` 是静态蓝图数据，在角色设计时声明，运行时不变。

---

## ECS 组件层（components.py）

`ArchetypeComponent` 继承自 `Component`（冻结/不可变），而非 `MutableComponent`，因为 Archetype 约束在整个地下城关卡期间不发生变化。  
该组件存储 `name`（角色名）和 `archetypes`（原型列表）两个字段。

---

## 组件挂载（tcg_game.py）

`ArchetypeComponent` 通过 `_mount_actor_archetype_components()` 在**实体创建时一次性挂载**，不允许重复调用。

**调用时机**：

| 调用点 | 挂载对象 |
| -------- | ---------- |
| `build_from_blueprint()` | 家园角色（玩家 + 盟友） |
| `setup_dungeon_entities()` | 地下城怪物（新创建后立即挂载） |

> **命名说明**：函数前缀用 `_mount_` 而非 `_ensure_`，明确表达"一次性挂载"语义，不是幂等的 ensure 操作。内部 `if entity.has(...)` 的 guard 仅用于处理两次调用时家园角色已有组件的情况，并非设计为可反复调用。

---

## 运行时集成（draw_cards_action_system.py）

### 采样逻辑

每次抽牌时，`_sample_archetypes()` 从 `ArchetypeComponent.archetypes` 池中**随机采样 `num_cards` 个原型**，每张牌对应一个约束：

- 池大小 ≥ `num_cards`：使用无放回采样，保证本轮不重复
- 池大小 < `num_cards`：使用有放回采样（目前 demo 角色各只有 1 个 archetype，均走此分支）

### Prompt 注入

`_build_design_principle_prompt()` 根据是否有采样结果生成不同内容：

- **有约束时**：在 prompt 中生成逐张约束列表，LLM 按位置一一对应
- **无约束时**：沿用原通用差异化指引（向后兼容，行为与引入 Archetype 前完全一致）

### 完整调用链

`react()` → `_create_draw_chat_client()` 读取实体的 `ArchetypeComponent`，调用 `_sample_archetypes()` 采样，再将结果传入 `_generate_draw_prompt()` → `_build_design_principle_prompt()` 注入约束段落 → `ChatClient.batch_chat()` 并行 LLM 推理 → `_process_draw_response()` 解析 JSON 写入 `HandComponent`。

---

## Demo 角色 Archetype 配置

| 角色 | 原型描述 |
| ------ | ---------- |
| 角色.旅行者.无名氏 | 多段连击型：每张卡牌优先生成多次攻击（hit_count ≥ 2），每段伤害较低但累积可观；格挡收益次要，damage_dealt 不为 0 |
| 角色.学者.维拉 | 状态控制型：每张卡牌的 status_effect_hint 不得为空，优先生成能引发持续状态（如虚弱、减速、灼烧）的卡牌；damage_dealt 可以偏低甚至为 0，以控场效果为核心价值 |
| 角色.怪物.沙狼 | 纯攻击型：所有卡牌以最大化 damage_dealt 为目标，block_gain 始终为 0，status_effect_hint 留空；target_type 仅使用 enemy_single |

---

## 扩展建议

- 每个角色可携带**多个 Archetype**，`_sample_archetypes` 的 `random.sample` 策略天然支持混合风格
- 未来可在 `Archetype` 模型中增加权重字段（`weight: float = 1.0`），实现加权随机采样
- Archetype 也可以在战斗中动态追加（如装备赋能），只需 `replace(ArchetypeComponent, ...)` 即可
