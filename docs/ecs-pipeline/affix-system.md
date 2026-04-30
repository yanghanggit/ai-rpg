# Affix 词条系统

> 本文档描述 Affix 词条机制的核心设计目标与跨类职责边界。  
> 上级入口：[[overview]]

---

## 设计动机：effects 与 affixes 的职责分离

`Card` 同时携带两种附加信息：`effects`（自然语言状态效果描述）与 `affixes`（结构化词条）。两者的受众不同——`effects` 是给 LLM 和人类读的叙事材料，驱动 `AddActorStatusEffectsActionSystem` 的推理；`affixes` 是给系统执行的机器可读约束，不经过 LLM 二次解释，直接被反序列化为 Component 并挂载到实体。

这一分离的关键意图是：**卡牌上的某些约束必须绕过 LLM 判断、由系统强制执行**。如果把"封印"只写在 `effects` 里，系统无法可靠地拦截出牌；写在 `affixes` 里，出牌/弃牌路径就能在服务层直接查询组件做守卫，不依赖任何 LLM 理解。

---

## 跨类协作的核心模式：生成 → 物化 → 查询

词条从生成到执行跨越三个层次，分属三类不同职责：

**生成层（DrawCardsActionSystem）**：LLM 在 `affixes` 字段里写入词条数据，系统在解析时做"宽进严出"验证——非法词条被静默丢弃而不崩溃管线，合法词条以 `ComponentSerialization` 保存在 `Card` 上。Prompt 不枚举具体词条名称，只说明格式规范，这样新增词条类型时无需改 Prompt。

**物化层（AffixSealedSystem）**：独立的 `ExecuteProcessor`，每帧将手牌中的词条"翻译"为实体级组件（如 `AffixSealedComponent`）。它之所以独立存在，是为了让所有下游系统（出牌、弃牌、敌方决策）都能直接查组件，而不是各自去扫描 `Card.affixes`。物化与来源无关——无论手牌从 LLM 生成、从历史牌组取出还是由场景注入，封印状态都由本系统统一维护。

**执行层（dungeon_actions 服务层）**：出牌和弃牌的入口函数在调用前检查 `AffixSealedComponent`，以强约束形式拒绝操作并返回明确错误。这是唯一需要"关心词条存在与否"的消费点，其他系统不需要感知词条。

---

## 可扩展性约定

词条系统的可扩展边界设计在 Component 注册机制上：每种词条对应一个 Component 类，用 `@register_component_type` 注册后即可被 LLM 在 `affixes` 中声明。新增词条类型不影响 Prompt 模板、不影响 `DrawCardsActionSystem` 解析逻辑，只需实现对应的物化系统和执行层守卫。

---

## 开发期 mock 的边界

`_inject_affix_sealed_mock_context` 只是端到端验证路径畅通的临时手段，不代表词条的正式触发机制。正式机制（装备赋能、场景效果、职业技能）都应通过游戏事件向 agent context 注入词条说明，驱动 LLM 在合适的时机写入 `affixes`；系统侧无需为不同触发来源做任何分支。
