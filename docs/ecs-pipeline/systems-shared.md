# 共享系统详解

> 本文档描述跨管线复用的公共 System。各管线文档中遇到这些 System 时均链接至此，不重复描述。  
> 上级入口：[[overview]]

---

## PrologueSystem

**类型**：`ExecuteProcessor`  
**位置**：每条管线的第一个 System  
**源码**：`src/ai_rpg/systems/prologue_system.py`

当前仅输出一条 debug 日志，作为管线执行的起始占位符。  
设计意图：未来可在此处统一添加前置检查、状态预热、链路追踪埋点等，不影响业务 System。

参见 [[design-patterns#1. 首尾夹持（Bookend Pattern）]]

---

## EpilogueSystem

**类型**：`ExecuteProcessor`  
**位置**：每条管线的最后一个 System  
**源码**：`src/ai_rpg/systems/epilogue_system.py`

执行两项操作：

1. **记录角色分布日志** — 遍历所有场景，输出每个场景内的角色名（含死亡状态标注）
2. **flush 实体状态** — 调用 `game.flush_entities()`，将运行时 Entity 数据同步回 `World` 数据模型（用于持久化/序列化）

参见 [[design-patterns#1. 首尾夹持（Bookend Pattern）]]

---

## ActorAppearanceUpdateSystem

**类型**：`ExecuteProcessor`（含并行 LLM 推理）  
**出现管线**：家园管线、战斗管线  
**源码**：`src/ai_rpg/systems/actor_appearance_update_system.py`

**触发条件**（状态守卫）：角色的 `AppearanceComponent.base_body` 不为空 **且** `appearance` 为空。

**执行流程**：

1. 筛选需要生成外观的角色实体
2. 从 `InventoryComponent` 读取装备类型物品（武器 / 防具 / 饰品）
3. 构建「基础形态 + 装备信息」的 System Prompt
4. 并行调用 LLM 生成完整外观描述（100-150字，第三人称，不含物品名称）
5. 写入 `AppearanceComponent.appearance`，并向角色上下文注入外观更新通知

参见 [[design-patterns#4. 并行 LLM 推理]]

---

## StageDescriptionSystem

**类型**：`ExecuteProcessor`（含并行 LLM 推理 + 磁盘缓存）  
**出现管线**：家园管线、战斗管线  
**源码**：`src/ai_rpg/systems/stage_description_system.py`

**触发条件**（状态守卫）：实体拥有 `StageComponent` 但**尚未持有** `StageDescriptionComponent`（懒加载模式）。

> stage 实体创建时不再默认添加 `StageDescriptionComponent`；本系统在首次 pipeline 执行时检测缺失并完成写入。  
> **强制刷新**：外部移除实体的 `StageDescriptionComponent` → 下一轮 pipeline 自动重新触发推理。

**执行流程**：

1. 收集有 `StageComponent` 且无 `StageDescriptionComponent` 的场景实体，并通过 `get_actor_appearances_in_stage()` 读取场景内所有角色的外观描述
2. 命中 debug 磁盘缓存（`enable_debug_cache=True` 时）则直接复用，跳过 LLM
3. 其余场景并行调用 LLM 生成环境描述，写入 `StageDescriptionComponent.narrative`

**Prompt 设计要点**：

- 角色外观作为「环境影响推断依据」传入（而非纯粹的角色信息），LLM 须分析其对场景环境的间接影响（如：持火把者 → 黑暗空间被照亮；发光生物 → 洞壁映出光晕）
- 若角色外观对场景环境有直接影响，该**环境效果**须体现在描述中
- 最终描述中不得出现任何角色名称、形态或行为，只输出纯粹的第三人称环境叙述

`enable_debug_cache` 参数在开发期避免重复调用 LLM，生产环境应关闭。

参见 [[design-patterns#3. 状态守卫（State Guard）]] · [[design-patterns#4. 并行 LLM 推理]]

---

## ActionCleanupSystem

**类型**：`ExecuteProcessor`  
**位置**：每条管线的倒数第三个（`DestroyEntitySystem` 之前）  
**源码**：`src/ai_rpg/systems/action_cleanup_system.py`

遍历 `ACTION_COMPONENT_TYPES` 注册表中的所有 Action 类型，从所有实体中移除它们，并通过断言验证清理完整性。

**注意**：新增 Action Component 类型时，必须同步注册到 `ACTION_COMPONENT_TYPES`，否则该 Action 不会被清理，会影响下一帧逻辑。

参见 [[design-patterns#2. Action 驱动的单帧消费模式]]

---

## DestroyEntitySystem

**类型**：`ExecuteProcessor`  
**位置**：每条管线的倒数第二个（`EpilogueSystem` 之前）  
**源码**：`src/ai_rpg/systems/destroy_entity_system.py`

查找所有挂有 `DestroyComponent` 的实体，逐个调用 `game.destroy_entity()` 将其从游戏世界中彻底移除。

使用 `entities.copy()` + `pop()` 的方式安全地在迭代中销毁实体，避免迭代器失效。销毁操作不可逆。
