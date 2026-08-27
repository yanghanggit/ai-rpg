# 卡牌关键词（keywords）

---

## 定位

keywords 是角色的牌库蓝图——设计者声明该角色可能拥有的全部卡牌风格，而非一张张具体卡牌。keywords 存于 `ArchetypeComponent`，是运行时不可变的约束，随角色实体贯穿战斗全程。archetype 是 keywords 的"总纲/容器"——定义"这个角色是什么流派"；`DeckComponent` 仅承载该流派产出的牌，规则归 archetype、牌归 deck。

---

## 设计原则

**字段级约束，不留模糊空间。** 一条 keyword 明确声明一张卡牌的功能边界，直接绑定到卡牌与状态效果的字段，而不是只给"适中""较低"这类形容词让 LLM 自行猜测。它完整声明四件事：

- 目标类型（打谁）；
- 伤害与出牌者攻击力的相对关系——以攻击力为基数、低于攻击力、或可为 0 与较低；
- 是否携带词缀及落点——无附加效果则不携带词缀；即时效果落在即时词缀（仅本次结算、不落地状态效果），跨回合效果落在延迟词缀（落地为 `StatusEffect`）；
- 若落地为状态效果，进一步声明其数值设计：生效阶段、持续回合数，以及数值挂靠哪个属性（防御增/减、速度升降）或写进哪段规则文本（如"受击时防御减半"这类乘性规则、"每回合末损失 N HP"这类周期规则）。

数值参考一律挂靠出牌者聚合后的属性（如"防御加成以本角色防御力为基数"），不在 keyword 里硬编码绝对值。牌库生成 LLM 拿到的是确定的字段落点与相对量级，而非需要二次解释的模糊措辞。

**通用化，不携带角色特化。** keyword 不写具体战斗形态与叙事内容，这些由角色的人设与外观（profile）承载。牌库生成时 LLM 同时读取 keyword（功能边界）与 profile（叙事意象），产出符合该角色的个性化卡牌；profile 是叙事主题的唯一权威来源。

**一效果一条，不分质量档。** 同一效果只保留一条普通档 keyword，不再并列"优质"变体。强度差异改由字段关系（如"低于攻击力"）或状态效果数值（如"持续三回合"）在单条 keyword 内表达，而不是靠同一效果的多条质量变体由采样碰运气。

---

## 流转

每场战斗，`GenerateDeckActionSystem` 从 `ArchetypeComponent.keywords` 池中采样与生成数量相等的条目，交由角色 LLM 按 keyword 的字段约束创作卡牌。生成数量由角色类型决定（远征队成员 5 张、怪物 3 张）；keywords 数量可大于单场生成数，未被采样的风格本场不出现——这是"固定风格池 + 每场抽样式变数"的牌库多样性机制。

→ 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)

---

## 与词缀的关系

keyword 直接声明词缀字段与文本：即时效果声明即时词缀（仅本次结算），跨回合效果声明延迟词缀并落到 `StatusEffect`。词缀文本（`[名称]:触发倾向描述`）由 keyword 给出，字段 schema 约束其格式。

→ 参见：[词缀（Affix）](affix.md)

---

## 跨系统关系

- keywords 在角色创建时声明，随角色实体挂载到 `ArchetypeComponent` → 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)
- `GenerateDeckActionSystem` 消费 keywords 产出具体 `Card` → 参见：[LLM 生成型游戏对象：Card 与 StatusEffect](llm-generated-objects.md)
- 副本怪物的 keywords 在副本工厂中声明 → 参见：[副本生成管道（Dungeon Generation Pipeline）](dungeon-generation.md)
