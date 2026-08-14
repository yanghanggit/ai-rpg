# 卡牌关键词（keywords）

---

## 定位

keywords 是角色的牌库蓝图——设计者声明该角色可能拥有的全部卡牌风格（如三张攻击、两张防御、一张破甲），而非一张张具体卡牌。这是"机制与内容分离"在牌库层的体现：设计者只写风格约束，具体卡牌的名称、描述、数值由角色 LLM 在牌库生成时按关键词创作。

keywords 存于 `DeckComponent`，是运行时不可变的约束，随角色实体贯穿战斗全程。

---

## 设计原则

**只写设计意图与时效语义，不写机制字段。** keyword 声明卡牌类型与效果的时效（即时破甲、持续侵蚀、持续一回合的防御），但不指定"通过 modifiers 还是 affixes 实现"。字段落点由宪法「词缀二分」与牌库生成提示词的字段 schema 决定，LLM 依据"即时→modifiers、跨回合→affixes"自行落到正确字段。

**通用化，不携带角色特化。** keyword 不写具体战斗形态（如纸人的竹签、朱砂），这些特化由角色的人设与外观描述承载。牌库生成时 LLM 同时读取关键词与角色 context，自然产出符合该角色的卡牌——通用 keyword 加特化 context，得到个性化牌库。

---

## 流转

每场战斗，`GenerateDeckActionSystem` 从 `DeckComponent.keywords` 池中采样与生成数量相等的条目，逐条配以 0–100 骰值，交由角色 LLM 创作卡牌。keywords 数量可大于单场生成数，未被采样的风格本场不出现——这是"固定风格池 + 每场抽样式变数"的牌库多样性机制；骰值仅在 keyword 声明使用骰值时叠加质量变体（失败 / 正常 / 优质）。

→ 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)

---

## 与词缀的关系

keyword 声明的卡牌类型决定该卡是否携带词缀：攻击型不带，防御 / 控制 / 侵蚀型带延迟词缀，破甲型带即时修正词缀。但 keyword 只表达"持续"或"即时"的时效语义，具体落到 modifiers 还是 affixes，由 LLM 依据宪法词缀二分在字段 schema 内完成。

→ 参见：[词缀（Affix）](affix.md)、[即时修正词缀（modifier）](modifier.md)

---

## 跨系统关系

- keywords 在角色创建时声明，随角色实体挂载到 `DeckComponent` → 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)
- `GenerateDeckActionSystem` 消费 keywords 产出具体 `Card` → 参见：[LLM 生成型游戏对象：Card 与 StatusEffect](llm-generated-objects.md)
- 副本怪物的 keywords 在副本工厂中声明 → 参见：[副本生成管道（Dungeon Generation Pipeline）](dungeon-generation.md)
