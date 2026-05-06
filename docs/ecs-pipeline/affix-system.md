# Affix 词条系统

> 本文档描述 Affix 词条机制的数据模型与执行守卫设计。  
> 上级入口：[[overview]]

---

## 数据模型：`Card.affixes`（`List[str]`）

`Card.affixes` 是每张牌上的自然语言词条列表，由 LLM 在抽牌阶段自由填写。每条词条为一个短语字符串，直接表达约束语义，例如：

- `"封印：不可出牌，不可弃牌"`
- `"诅咒：每回合开始扣 1 HP"`

`affixes` 与 `effects` 职责不同：`effects` 是给仲裁 LLM 和玩家阅读的叙事材料，驱动 `AddActorStatusEffectsActionSystem` 推理；`affixes` 是给服务层直接裁决的约束规则，以自然语言字面语义传递给 LLM 守卫，无需反序列化。

---

## 执行守卫：`_check_affixes_allow_action`

`_check_affixes_allow_action` 是 `dungeon_actions.py` 服务层的异步辅助函数，在 `activate_play_cards_specified` 和 `activate_discard_cards_specified` 入口处被调用，判断当前手牌词条是否允许本次操作。

执行逻辑：

1. 收集手牌所有卡牌的词条规则（格式：`[卡牌名] 词条内容`），无词条时直接放行
2. 构建 markdown 格式 prompt（`## 节标题` + 明确 JSON 示例），调用 `DeepSeekClient.async_chat()`
3. 用 `extract_json_from_code_block` 提取响应中的 JSON，`_AffixGuardResponse(BaseModel)` 做 Pydantic 校验
4. `allowed == False` 时记录 WARNING 并将 `reason` 向上抛出；LLM 推理异常时 fail-open 放行，保证操作不因 LLM 故障阻塞

`_AffixGuardResponse` 字段：`allowed: bool`、`reason: str`。

---

## 可扩展性约定

词条系统的扩展完全在语义层：新增词条只需在 agent context 中引入新的自然语言描述（如 `"枷锁：仅可被弃牌"`），守卫 prompt 会将手牌上所有词条逐条传入，LLM 凭字面语义裁决。系统侧无需注册新类型或修改守卫代码。

---

## 开发期 mock 的边界

`_mock_inject_sealed_affix_context` 只是端到端验证路径畅通的临时手段：Round 1 时向所有 `PartyMemberComponent` 注入封印词条文本示例，引导 LLM 在某张牌的 `affixes` 中填入该词条；后续出牌时守卫即可触发。

正式的词条触发机制（装备赋能、场景效果、职业技能）都应通过游戏事件向 agent context 注入词条说明，驱动 LLM 在合适时机写入 `affixes`；系统侧无需为不同触发来源做任何分支。
