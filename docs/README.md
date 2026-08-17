# AI-RPG 知识库根节点

> 这是 `docs/` 目录的唯一入口。每次新增文档领域时，请在此处更新索引。
> Agent 从此处出发，可定位到任何知识。
>
> **写作约束（AI 编写文档时必须遵守）**
>
> **写什么**
>
> - 写**设计意图与架构决策**：解释"为何这样设计"、"与哪些系统交互"，不描述实现步骤。代码已能自述的细节不再复述。
> - 写**跨系统关联**：本系统如何被其他系统驱动、产出被谁消费。单系统内部的步骤逻辑靠代码阅读。
> - 写**相对稳定的知识**：核心类名（如 `GearItem`、`EquippedGearComponent`）可用行内代码引用；变量名、函数名、字段名随实现变化，引用它们等于复述代码，应规避。
> - 写**紧凑精要**：追求信息密度，避免铺陈。一段文字如果删掉后设计意图仍然完整，就该删。
>
> **怎么写**
>
> - 禁止代码块（` ``` `）。
> - 交叉引用格式：`→ 参见：[文档标题](相对路径)`，置于段落末或独立行。
> - 每篇聚焦一个系统；跨系统对比用交叉引用表达，不在同文档内做横向对比表。
>
> **何时新建文档**
>
> - 新增文档的条件：出现了一个独立的设计概念，其意图和关联无法用现有文档的一两段话说清。
> - 否则更新已有文档。新建后立即更新本页索引。

---

## 知识领域索引

### wiki/ — 核心系统设计

| 文档 | 简介 |
| ------ | ------ |
| [消耗品系统（ConsumableItem）](wiki/consumable-item.md) | 消耗品的数据模型、战斗使用管道、词缀机制设计 |
| [装备系统（GearItem）](wiki/gear-item.md) | 装备的数据模型、移动语义装备管道、EquippedGearComponent 生命周期 |
| [工坊合成管道（Craft Pipeline）](wiki/craft-pipeline.md) | 工坊合成的核心哲学：机制与内容分离、配置注入路径、材料驱动的创意生成 |
| [材料系统（MaterialItem）](wiki/material-item.md) | 材料的数据模型、工坊合成管道（消耗品/装备/时装三类产物）、与其他物品类型的关系 |
| [AI 操作 CLI（run_agent_game.py）](wiki/run-agent-game.md) | 快照驱动设计的意图、AI 代理操作工具与 TUI 客户端的分工 |
| [副本生成管道（Dungeon Generation Pipeline）](wiki/dungeon-generation.md) | 核心哲学：机制与内容分离、四步接力管道的分工意图与设计决策、与工坊合成的架构对比 |
| [战斗管道（Combat Pipeline）](wiki/combat-pipeline.md) | ECS 处理器链的架构设计：管道心跳驱动、场景实体仲裁、词缀因果链、回合行动序列与四个生命周期阶段 |
| [卡牌关键词（keywords）](wiki/keywords.md) | 角色牌库蓝图：风格池声明、设计原则（不写机制/不携带特化）、牌库多样性与骰值 |
| [词缀（Affix）](wiki/affix.md) | 词缀作为 StatusEffect 种子的创建、流转、落地与回述全线路 |
| [LLM 生成型游戏对象：Card 与 StatusEffect](wiki/llm-generated-objects.md) | 两类 LLM 动态产出的核心对象的生成点定位、全局约束视角、生成链与规则来源 |
| [公共知识检索系统（RAG / QueryAction）](wiki/rag-knowledge-base.md) | 公共记忆与私人记忆的二元分离、Blueprint.knowledge_base 的编排约束、ChromaDB 两阶段生命周期、QueryActionSystem 的触发与消费 |
| [新故事设计：《大渊》](wiki/新故事设计.md) | 新故事世界观草稿：双重世界（济世疗养院 / 大傩）、核心冲突、角色设定与玩法方向 |
