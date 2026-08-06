# LLM 生成型游戏对象：Card 与 StatusEffect

---

## 定位

战斗管道中有两类核心游戏对象完全由 LLM 生成：卡牌（`Card`）和状态效果（`StatusEffect`）。它们不是静态配置，而是在战斗运行时由不同 Agent 在不同阶段动态产出，并由统一的约束规则（`RPG_SYSTEM_RULES` 战斗专用规则）规范其形态。

`Card` 是一次性动作载体，出牌即消耗，效果在本次结算中体现。`StatusEffect` 是持续性载体，跨回合生效，修改角色的 `duration` / `speed` / `defense` / `counter` 等数值。

→ 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)（完整管道结构与各阶段职责）

---

## 全局约束视角

尽管 Card 和 StatusEffect 的生成散布在不同系统中，它们共享一组相同的底层规则（来自 `RPG_SYSTEM_RULES` 战斗专用规则）。Agent 无论以何种角色（角色自身 vs 场景实体）在何种时机（战斗初始化 vs 仲裁后）生成这些对象，都必须遵守：

### 词缀二分

modifiers 与 affixes 平级但时效不同。modifiers 是对本次结算的一次性数值修正（如无视防御、伤害加成），不产生持续状态。affixes 是延迟触发信号，出牌后由独立推理落地为 StatusEffect。Agent 生成 Card 时必须区分两者，禁止在 modifiers 中写入跨回合表述（「下回合」「持续N回合」），禁止在 affixes 中写入可直接量化的数值。

### 载体二分

Card 与 StatusEffect 是仅有的两类游戏机制载体。Card 代表一次动作，其 `damage_dealt` / `energy_delta` / `hit_count` 是确定性数值，`description` 是叙事包装。StatusEffect 代表持续影响，通过 `phase` 字段决定生效阶段——`DRAW` 调整抽牌、`ARBITRATION` 影响仲裁结算、`ROUND_END` 每回合末 tick。

### affixes → StatusEffect 因果链

affix 不是 StatusEffect 本身，而是触发信号。这条因果链贯穿多个系统：Card 生成时写入 affixes（因）→ 仲裁后 `AddStatusEffectsActionSystem` 将 affix 推理为 StatusEffect（果）。Agent 生成 Card 的 affixes 时写的是一段触发倾向描述，下游 Agent 生成 StatusEffect 时将其落地为具体的 `phase` / `duration` / `defense` 等字段。

### 禁止的表述与机制

回合制无位置与命中判定——禁止「命中率」「闪避」「移动」「位置」等概念。根属性不可扩展——StatusEffect 只能修改 `duration` / `speed` / `defense` / `counter` / HP（ROUND_END），禁止引入新的数值轴（火焰抗性、暴击率等）。

---

## Card 的 LLM 生成点

### 1. 初始牌库生成（GenerateDeckActionSystem）

**触发时机**：战斗初始化阶段，`CombatInitActorSystem` 为每个参战角色挂载 `GenerateDeckAction`。

**生成者**：每个角色自身的 LLM Agent。

**输入约束**：关键词（`DeckComponent.keywords`）+ 骰值（0–100 随机）。关键词定义牌型风格——「纯攻击型：不携带任何附加效果」vs「即时破甲型：必须携带 modifier」。骰值决定质量档位（失败/正常/优质），影响 `damage_dealt` 的量级。

**prompt 构建**：`card_prompt_builders.generate_deck_prompt`，包含角色属性表、卡牌字段说明、JSON 示例（空 modifiers/affixes）、约束列表。

**输出**：`DeckCardEntry` 列表，按顺序对应关键词和骰值。每张牌需填充全部字段：`name` / `description` / `affixes` / `modifiers` / `playable` / `exhaust` / `cost` / `damage_dealt` / `energy_delta` / `hit_count` / `target_type`。

**关键词-骰值示例**：骰值 28（失败）→ `damage_dealt` 偏低（如 3），骰值 97（优质）→ `damage_dealt` 显著高于基础 attack（如 8–9）。

### 2. 场景塞牌（InjectCardsActionSystem）

**触发时机**：每次仲裁结算后（同一帧内），由场景实体统一评估。

**生成者**：场景实体（stage entity）的 LLM Agent。

**输入**：场内存活角色的 HP/状态效果摘要 + 上下文中的仲裁叙事文本（来自 `PlayCardsArbitrationSystem` 的 combat_log 和 narrative）。

**判断逻辑**：仅可将叙事中已明确描述的环境要素（沙尘入眼、碎石可用、断柱可借力）转化为卡牌。需先推断物件当前状态（完好/已损耗/不可用），不可用时应设 `playable: false`。无可用要素时必须输出空数组。

**特点**：`exhaust` 通常设为 `true`（一次性机遇），`source` 固定为场景实体名，注入目标为对应角色的 `DiscardPileComponent`（不会直接进入手牌）。

**与初始牌库的区别**：场景塞牌的 prompt 不含关键词约束，而是由战斗叙事驱动；生成者是场景实体而非角色自身；产出注入弃牌堆而非牌库。

---

## StatusEffect 的 LLM 生成点

### 1. 战斗初始化场景效果（CombatInitStageSystem）

**触发时机**：战斗状态从 `INITIALIZING` 切换到 `ONGOING` 时。

**生成者**：场景实体的 LLM Agent。

**输入**：场景叙事文本 + 参战角色名单。

**判断逻辑**：检查叙事中是否存在可转化为状态效果的要素（浓烟、灼热地面、毒雾、冰水等）。仅当叙事明确描述时才能生成，必须输出空对象而非凭空引入。禁止角色内在情绪或来源不明的魔法效果。

**输出格式**：`[场景]` 词缀文本（20–40 字），作为 `AffixTrigger` 交由 `AddStatusEffectsActionSystem` 生成实际 StatusEffect。本阶段只产生词缀信号，不直接生成 StatusEffect。

### 2. 词缀落地（AddStatusEffectsActionSystem）

**触发时机**：仲裁结算后，每次出牌 / 使用消耗品 / 使用装备的 affix 触发 + 场景交互词缀 + 战斗初始化场景词缀，同一 tick 内合并处理。

**生成者**：每个受影响角色自身的 LLM Agent。

**输入**：`AffixTrigger` 列表（含来源信息——卡牌名/装备名/场景交互上下文）+ 角色当前已有的 StatusEffect 列表。

**核心约束**：**严格 1:1 映射**——N 条 AffixTrigger 必须产出 N 个 StatusEffect，顺序一一对应。LLM 必须指定每个效果的 `phase` 字段，这决定了该效果被下游哪个系统消费。

**phase 的三种消费路径**：

- `DRAW`：由 `PostDrawCardsSystem` 消费。`description` 须给出可执行的手牌调整规则（「本回合手牌费用 +1」「本回合手牌伤害 -2」），由另一个 LLM 按该规则修改已抽手牌数值。
- `ARBITRATION`：由 `PlayCardsArbitrationSystem` 消费。`description` 须是仲裁 LLM 能直接套用的规则（「荆棘：对攻击者造成 2 点反伤」「护盾：本次受击伤害 -3」）。可用 `counter` 字段实现条件计数（「前 3 次受击伤害变为 1」→ `counter: 3`，由仲裁 LLM 按事件递减）。
- `ROUND_END`：由 `CombatRoundEndEffectSettlementSystem` 消费。仅影响 HP，`description` 须是可被 LLM 解析的 HP 增减规则（「每回合末损失 2 HP」「每回合末恢复 1 HP」）。

**通用字段**：`duration`（-1 永久 / >0 剩余回合）、`speed`（持续叠加到出手速度）、`defense`（持续叠加到防御值）。禁止修改 `max_hp`。

---

## 生成链：Card → affix → StatusEffect

一条完整的生成链路展示了两类对象如何衔接：

1. `GenerateDeckActionSystem` 生成 Card，其 `affixes` 字段写入触发描述（如「呛咳:呼吸不畅，下回合手牌伤害 -2」）。
2. 该 Card 被打出后，`PlayCardsArbitrationSystem` 结算伤害，同时将 `affixes` 转为 `AffixTrigger`（含来源上下文）。
3. `AddStatusEffectsActionSystem` 收到 `AffixTrigger`，调用 LLM 推理落地的 StatusEffect——对上例可能生成一个 `phase=DRAW`、`duration=1`、`description='本回合手牌伤害 -2'` 的效果。
4. 下一回合抽牌后，`PostDrawCardsSystem` 消费该 DRAW 效果，修改手牌数值。

这条链上，Step 1 的 Card 生成者需要理解「affix 是信号不是效果」，Step 3 的 StatusEffect 生成者需要将信号转化为有 `phase` 的完整效果，Step 4 的消费者需要理解效果的 `description` 规则。全局约束在此处的作用是保证三者使用相同的语义约定。

---

## 生成规则来源

所有 Card 和 StatusEffect 的生成约束最终都追溯至两个源头：

- **系统级**：`RPG_SYSTEM_RULES` 的战斗专用规则节，通过 entity factory 烤入每个实体的 system message。Agent 从对话首条消息就携带这些规则，无需运行时注入。
- **prompt 级**：各系统的 prompt builder 函数（`card_prompt_builders` / `arbitration_prompt_builders` / `add_status_effects_action_system` 内嵌函数）在每次 LLM 调用时附加字段说明、JSON schema、约束列表等即时指引。

prompt 级的约束是系统级规则的实例化和细化。例如系统规则说「词缀二分」，prompt 级则给出 `modifiers` 和 `affixes` 各自允许和禁止的表述形式。
