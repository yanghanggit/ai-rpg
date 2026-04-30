# AI-RPG 知识库根节点

> 这是 `docs/` 目录的唯一入口。每次新增文档领域时，请在此处更新索引。
> Agent 从此处出发，可定位到任何知识。
> **写作约束（AI 编写文档时必须遵守）**
    > - `docs/` 记录的是**相对稳定的设计知识**，不是代码快照。
    > - 禁止在文档中出现代码块（` ``` `）。类名、函数名等符号用行内代码（`` ` `` ）提及即可。
    > - 设计意图、架构决策、调用时序等文字描述 > 任何形式的代码示意。

---

## 项目简介

**ai-rpg** 是一款融合 TCG 卡牌战斗机制的 AI 驱动 RPG 游戏。  
核心技术栈：Python · ECS（自研 entitas） · LangChain · ChromaDB · FastAPI

关键概念：`Entity` / `Component` / `System` / `Pipeline` / `ReactiveProcessor` / `LLM Agent`

---

## 知识领域索引

| 领域 | 内容摘要 | 入口文档 |
| ------ | ---------- | ---------- |
| **ECS 管线设计** | 三条游戏流程管线（家园/战斗/地牢生成）的架构、系统执行顺序与设计模式 | [ecs-pipeline/overview.md](ecs-pipeline/overview.md) |
| **Keyword 卡牌关键词约束系统** | 角色卡牌生成风格约束的数据模型、ECS 组件、采样策略与 Prompt 注入机制 | [ecs-pipeline/keyword-system.md](ecs-pipeline/keyword-system.md) |
| **Affix 卡牌词条系统** | 卡牌词条数据模型（`Card.affixes: List[str]`，自然语言字符串）、LLM 生成、服务层 LLM 词条守卫（`_check_affixes_allow_action`），以及开发期 mock 引导说明 | [ecs-pipeline/affix-system.md](ecs-pipeline/affix-system.md) |

---

## 更新日志

| 日期 | 变更 |
| ------ | ------ |
| 2026-04-30 | 新增 Affix 词条系统：`Card.affixes`（`List[str]`，自然语言词条）；出牌/弃牌路径新增服务层 LLM 词条守卫 `_check_affixes_allow_action`（`_AffixGuardResponse` Pydantic 校验，markdown prompt 风格，`extract_json_from_code_block` 提取）；`_mock_inject_sealed_affix_context` 开发期 mock（Round 1 向远征队员注入封印词条文本）；新增 `docs/ecs-pipeline/affix-system.md` |
| 2026-04-30 | 新增弃牌机制 `DiscardCardsActionSystem`（步骤 9）：将手牌移入 `DiscardDeckComponent`，不消耗 energy，不推进行动顺序；source 守卫与出牌路径对称（自有牌归档 + 注入上下文，外来牌静默丢弃）；`DiscardDeckComponent` 由"保留备用"升级为主动弃牌堆。`DrawCardsActionSystem` 新增 LLM 解析失败兜底机制（兜底牌「等待」，`SELF_ONLY`），确保 `HandComponent` 始终写入、回合不阻塞；`pipeline-combat.md` 新增 `DiscardCardsActionSystem` 详解，步骤编号同步更新（原步骤 9→10，余类推） |
| 2026-04-28 | `PostArbitrationActionSystem` 升级为双路径架构：`filter()` 扩展为 Stage OR Actor；`react()` 内部按顺序执行两个批次（Stage 批次：LLM 地牢主视角干预；Actor 批次：暂为 stub，触发点未实装）；类名/模块注释与 `pipeline-combat.md` 同步更新 |
| 2026-04-27 | 移除 `CombatInitializationSystem` 的"创建第一回合"职责，改由 `CombatRoundTransitionSystem` 在同帧末端统一创建（消除初始化死锁）；`Round` 数据模型以 `actor_order_snapshots`（快照列表）+ `current_actor_name` 替代原 `action_order`；新增 `CombatRoundCompletionSystem`（energy-based 判断）；`pipeline-combat.md` 补充步骤 13、调整步骤编号 13→16 并新增 `CombatRoundCompletionSystem` 与 `CombatRoundTransitionSystem` 详细说明；`design-patterns.md` 更新状态守卫表 |
| 2026-04-24 | `DrawCardsActionSystem` 新增 `use_compressed_prompt` 开关（默认 `True`）：对话历史存压缩版 prompt，静态字段说明与 JSON 示例以 `draw_cards_full_prompt` 附挂；新增 `_generate_compressed_draw_prompt`；更新 `pipeline-combat.md` |
| 2026-04-21 | `HomeActorPlanSystem` 新增 `use_compressed_prompt` 开关（默认 `True`）：对话历史存压缩版 prompt，完整版以 `home_actor_full_prompt` 附挂；`ActionPlanResponse` 补全 `inspect_self` / `equip_weapon` / `equip_armor` / `equip_accessory` 字段；`_PLAYER_ACTIVE_ACTION_TYPES` 补入 `EquipItemAction`；更新 `pipeline-home.md` |
| 2026-04-15 | 新增 `CardTargetType.ENEMY_RANDOM_MULTI`（多段随机命中）；`dungeon_actions._resolve_targets` 与 `EnemyPlayDecisionSystem` 均改用 `match` 分发；`arbitration_action_system` 提取 `_fmt_duration` / `_fmt_effects` / `_build_random_multi_sections` 为模块级函数；`pipeline-combat.md` 新增"卡牌目标类型（CardTargetType）"章节 |
| 2026-04-14 | 新增 `DiceValue(IntEnum)`（`MIN=0`/`MAX=100`）；`DrawCardsActionSystem` 每回合按 `DiceValue` 范围生成骰值，逐张注入 prompt；`_build_design_principle_prompt` 支持骰值附加与兜底说明；更新 `archetype-system.md`、`pipeline-combat.md` |
| 2026-04-30 | 新增 `PlayedDeckComponent`（已出牌统计）；出牌归档目标从 `DiscardDeckComponent` 改为 `PlayedDeckComponent`；`DiscardDeckComponent` 保留备用；`_mount_actor_deck_components()` 同步挂载新组件；`overview.md`、`pipeline-combat.md` 同步更新 |
| 2026-04-28 | 将 `Archetype`/`ArchetypeComponent`/`archetypes` 全面更名为 `Keyword`/`KeywordComponent`/`keywords`；`docs/ecs-pipeline/archetype-system.md` 重命名为 `keyword-system.md` |
| 2026-04-13 | 初始化知识库；新增 `ecs-pipeline/` 系列文档（7 篇） |
