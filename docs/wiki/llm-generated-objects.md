# LLM 生成型游戏对象：Card 与 StatusEffect

---

## 定位

战斗管道中有两类核心游戏对象完全由 LLM 在运行时动态产出：`Card`（战斗行动单元）和 `StatusEffect`（持续性状态载体）。它们不是静态配置数据，而是由不同 Agent 在不同阶段生成，受同一套全局规则约束。理解它们的生成点与约束链，是理解战斗如何被「创作」而非「计算」的关键。

→ 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)（完整管道结构与各阶段职责）

---

## 全局约束体系

生成约束分两层，Agent 无论以何种角色在何时生成，都必须穿透两层：

**系统级**：`RPG_SYSTEM_RULES` 的战斗专用规则节，通过 entity factory 烤入每个实体的 system message。这是 Agent 的「世界观宪法」——从对话首条消息就携带，无需运行时注入。核心条款：

- 词缀（affix）：affix 是不含可直接量化数值的触发信号，按时效分两类——即时 affix（`on_play_affixes`/`on_use_affixes`）参与本次仲裁、不落地 StatusEffect；延迟 affix（`on_hit_affixes`）后续独立推理落地为 StatusEffect。
- 载体二分：Card 是一次性效果载体，StatusEffect 是持续影响。一切跨回合效果必须落地为 StatusEffect。
- 延迟 affix → StatusEffect 因果：延迟 affix 是因，StatusEffect 是果，不可跳过落地步骤；即时 affix 只在本次仲裁套用。
- 禁止项：命中率、闪避、位置、移动、新数值轴。

**prompt 级**：各系统的 prompt builder 在每次 LLM 调用时附加字段 schema、JSON 示例、具体约束。prompt 级是系统级的实例化——系统级说「词缀（affix）」，prompt 级给出即时/延迟词缀字段允许和禁止的表述形式。

---

## Card 生成

### 初始牌库（GenerateDeckActionSystem）

**生成者**：角色自身 LLM。设计意图：每个角色的牌库由角色自己「想」出来，牌名和描述反映该角色的战斗风格与个性。

**驱动因子**：关键词（`ArchetypeComponent.keywords`）+ 叙事主题（从角色设定 profile 提炼）。

`ArchetypeComponent.keywords` 是角色的**完整牌库蓝图**（规则层）——设计者在此声明该角色可能拥有的全部卡牌风格（如 3 张攻击、2 张防御、1 张破甲）。同一效果的不同质量档位（如普通穿甲 / 优质穿甲）直接写为两条独立的 keyword 文本，一并存入池中。每场战斗实际生成几张牌，由 `get_cards_per_combat(entity)` 根据角色类型（PartyMember / Monster）决定；系统从 keywords 池中随机采样对应数量后交由 LLM 创作具体卡牌。

这意味着：keywords 数量可以大于单场战斗生成数，未被采样的 keyword 在本场不会出现——这是设计层面的「牌库多样性」机制：角色有固定风格池，但每场战斗抽到哪些风格存在变数。同一效果的质量变体也作为独立条目存在于池中，因此同一场战斗有可能同时抽中多个质量档位。

这是「机制与内容分离」的体现——角色设计者只需写关键词（纯攻击型 / 破甲型），具体卡牌名称、描述、数值由 LLM 按关键词创作。

**Card 的三层结构**：规则（affixes）、数值（damage / hit_count / cost / target_type）、叙事（description）。三者职责正交——keywords 约束规则层，数值由字段 schema 决定，description 是叙事锚点，可自由采用动作、物件、意象、氛围、典故等任意形态，不限于动作句。叙事主题由角色 LLM 在生成时从自身「角色设定」（profile）提炼，profile 是叙事意象的唯一权威来源。

**消费方**：产出直接写入 `DeckComponent` 和 `DrawPileComponent`，被 `DrawCardsActionSystem` 抽入手中。description 的下游消费方是出牌仲裁（`PlayCardsArbitrationSystem`）：仲裁 prompt 读入 description，结合场景环境、目标状态与即时词缀做「故事泛化」生成 narrative——description 只影响叙事演出，不改变确定性数值结算。

### 场景塞牌（InjectCardsActionSystem）

**生成者**：场景实体 LLM。设计意图：让环境成为战斗参与者——叙事中描述过的物件（碎石、断柱、沙尘）可以在仲裁后被场景实体转化为可出牌，实现环境与角色的深层交互。

**驱动因子**：仲裁叙事文本 + 场内存活角色状态。仅可将叙事中已明确描述的环境要素转化为卡牌，必须先推断物件当前状态（完好/已损耗），不可用时设 `playable: false`。无可用要素必须输出空数组。

**与初始牌库的核心差异**：生成者是场景实体而非角色自身，驱动因子是叙事上下文而非关键词，产出注入 `DiscardPileComponent`（不直接进手牌），`exhaust` 通常为 `true`（一次性机遇）。

**消费方**：塞入的牌在后续回合中经抽牌进入手牌，由角色正常打出。

---

## StatusEffect 生成

### 场景初始化效果（CombatInitStageSystem）

**生成者**：场景实体 LLM。设计意图：战斗场景本身可以有「地形效果」——浓烟、灼热地面、冰水——在战斗开始时就对角色产生持续影响。

**输出形式**：`[场景]` 词缀文本，作为 `AffixTrigger` 交由 `UpdateStatusEffectsActionSystem` 落地。本阶段只产信号不产生效果，保持与仲裁后词缀链的统一。

### 词缀落地（UpdateStatusEffectsActionSystem）

**生成者**：受影响角色自身 LLM。设计意图：延迟 affix 是外源触发（来自卡牌 / 装备 / 场景），但最终以什么形态影响该角色，由角色自己推理——同一根毒刺扎在不同角色身上，落地效果应由目标体质决定。

**核心约束**：严格 1:1 映射——N 条 `AffixTrigger` 必须产出 N 个 StatusEffect。每个效果须指定 `phase`，决定被哪个下游系统消费：

- `DRAW`：消费方 `PostDrawCardsSystem`，按 description 调整刚抽到的手牌
- `ARBITRATION`：消费方 `PlayCardsArbitrationSystem`，在仲裁结算中生效。可用 `counter` 实现条件计数
- `ROUND_END`：消费方 `CombatRoundEndSettlementSystem`，每回合末 tick HP

**通用字段**：`duration` / `speed` / `defense` 持续影响角色数值。禁止修改 `max_hp`。

---

## 生成链

完整链路展示两类对象如何衔接——也揭示了为什么全局约束必须一致：

> Card 生成者写入即时词缀（`on_play_affixes`，本次仲裁套用）与延迟词缀（`on_hit_affixes`，信号）→ 延迟词缀仲裁时转为 `AffixTrigger` → `UpdateStatusEffectsActionSystem` 推理落地 StatusEffect（持续效果）→ 按 phase 分发消费者（`PostDrawCardsSystem` / `PlayCardsArbitrationSystem` / `CombatRoundEndSettlementSystem`）

链上三个 Agent 使用不同的上下文（角色自身 vs 场景实体）、在不同阶段工作，但必须共享同一套语义约定——这就是全局约束体系存在的根本原因。
