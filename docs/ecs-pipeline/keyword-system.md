# Keyword 卡牌关键词约束系统

> 本文档描述 Keyword 机制的数据模型、ECS 组件设计与在 DrawCardsActionSystem 中的集成方式。  
> 上级入口：[[overview]]

---

## 背景与设计目标

默认情况下，LLM 为每个角色生成手牌时只依赖角色自身的 system message + 战斗上下文，风格完全自由。  
Keyword 机制在此基础上引入**一组自然语言约束规则**，限定 LLM 每次生成卡牌时必须遵循的风格与功能边界。

**典型效果**：

- 多段连击型 → 每张牌的 `hit_count ≥ 2`
- 状态控制型 → 每张牌的 `status_effect_hint` 不为空
- 纯攻击型 → `block_gain` 始终为 0，`damage_dealt` 最大化

---

## 数据模型层（entities.py）

`Keyword` 是一个 Pydantic `BaseModel`，只有一个字段 `description`，存储自然语言约束规则。  
`Actor` 模型通过 `keywords: List[Keyword]` 字段携带约束列表，默认为空列表（即无约束）。

`keywords` 是静态蓝图数据，在角色设计时声明，运行时不变。

`DiceValue` 是 `IntEnum`，定义骰值的范围常量：`MIN = 0`、`MAX = 100`。骰值是纯运行时随机数，不属于静态蓝图，无需持久化，仅在 `_create_draw_chat_client()` 内按需生成。

---

## ECS 组件层（components.py）

`KeywordComponent` 继承自 `Component`（冻结/不可变），而非 `MutableComponent`，因为 Keyword 约束在整个地下城关卡期间不发生变化。  
该组件存储 `name`（角色名）和 `keywords`（关键词列表）两个字段。

---

## 组件挂载（tcg_game.py）

`KeywordComponent` 通过 `_mount_actor_keyword_components()` 在**实体创建时一次性挂载**，不允许重复调用。

**调用时机**：

| 调用点 | 挂载对象 |
| -------- | ---------- |
| `build_from_blueprint()` | 家园角色（玩家 + 盟友） |
| `setup_dungeon_entities()` | 地下城怪物（新创建后立即挂载） |

> **命名说明**：函数前缀用 `_mount_` 而非 `_ensure_`，明确表达"一次性挂载"语义，不是幂等的 ensure 操作。内部 `if entity.has(...)` 的 guard 仅用于处理两次调用时家园角色已有组件的情况，并非设计为可反复调用。

---

## 运行时集成（draw_cards_action_system.py）

### 采样逻辑

每次抽牌时，`_sample_keywords()` 从 `KeywordComponent.keywords` 池中**随机采样 `num_cards` 个关键词**，每张牌对应一个约束：

- 池大小 ≥ `num_cards`：使用无放回采样，保证本轮不重复
- 池大小 < `num_cards`：使用有放回采样（目前 demo 角色各只有 1 个 keyword，均走此分支）

### Prompt 注入

`_build_design_principle_prompt()` 根据是否有采样结果及是否传入骰值，生成不同内容：

- **有约束时**：在 prompt 中生成逐张约束列表，LLM 按位置一一对应；若同时传入骰值（长度与 keywords 相同），则在每行末尾附加 `（骰值：N）`，并在段落 header 中注明"骰值仅在约束中明确说明用法时生效，否则忽略"
- **无约束时**：沿用原通用差异化指引，不附骰值（向后兼容，行为与引入 Keyword 前完全一致）

骰值的语义完全由各角色自己的 `Keyword.description` 决定。若 description 未提及骰值用法，LLM 依兜底说明忽略该数字，骰值对生成结果无副作用。这赋予了 Keyword 设计者通过 description 文本声明骰值映射规则（如"骰值 < 30 时生成防御牌，≥ 30 时生成攻击牌"）的能力，而无需修改系统代码。

### 完整调用链

`react()` → `_create_draw_chat_client()` 读取实体的 `KeywordComponent`，调用 `_sample_keywords()` 采样，生成 `dice_rolls`（每张牌一个 `DiceValue.MIN`～`DiceValue.MAX` 随机整数），再将两者传入 `_generate_draw_prompt()` → `_build_design_principle_prompt()` 注入约束段落（含骰值） → `ChatClient.batch_chat()` 并行 LLM 推理 → `_process_draw_response()` 解析 JSON 写入 `HandComponent`。

---

## Demo 角色 Keyword 配置

| 角色类型 | 关键词描述 |
| ------ | ---------- |
| 多段连击型（旅行者） | 每张卡牌优先生成多次攻击（hit_count ≥ 2），每段伤害较低但累积可观；格挡收益次要，damage_dealt 不为 0 |
| 状态控制型（学者） | 每张卡牌的 status_effect_hint 不得为空，优先生成能引发持续状态（如虚弱、减速、灼烧）的卡牌；damage_dealt 可以偏低甚至为 0，以控场效果为核心价值 |
| 纯攻击型（怪物） | 所有卡牌以最大化 damage_dealt 为目标，block_gain 始终为 0，status_effect_hint 留空；target_type 仅使用 enemy_single |

---

## 扩展建议

- 每个角色可携带**多个 Keyword**，`_sample_keywords` 的 `random.sample` 策略天然支持混合风格
- 未来可在 `Keyword` 模型中增加权重字段（`weight: float = 1.0`），实现加权随机采样
- Keyword 也可以在战斗中动态追加（如装备赋能），只需 `replace(KeywordComponent, ...)` 即可
- `Keyword.description` 可声明骰值的具体映射语义（如"骰值 < 30→防御型；≥ 30→攻击型"），系统无需任何代码改动即可支持基于骰值的条件分支风格约束
- `DiceValue.MIN / MAX` 当前为 0 / 100；如需支持其他范围（如模拟 D6：1-6），只需修改常量即可，生成逻辑不用改
