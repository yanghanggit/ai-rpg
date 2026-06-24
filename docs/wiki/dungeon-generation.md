# 地下城生成流程（Dungeon Generation Pipeline）

地下城生成是一条由五个 `ReactiveProcessor` 依次接力的异步流水线。每一步通过向实体添加 Action 组件触发下一步，中间产物以 JSON 文件落盘，便于调试与回溯。整条链路的设计原则是：**LLM 在前三步承担文本创作，第四步是纯数据组装，第五步负责图片生成**。

---

## 流水线总览

GenerateDungeonAction → 第一步（生态） → GenerateDungeonStagesAction → 第二步（场景） → GenerateDungeonActorsAction → 第三步（角色） → AssembleDungeonAction → 第四步（组装） → IllustrateDungeonAction → 第五步（插画）

每步的中间文件写入 `DUNGEON_PROCESS_DIR`（`DEBUG_CACHE_DIR/_process/`），文件名格式为 `{地下城名}_step{N}_*.json`，最终成品写入 `DUNGEONS_DIR`。

---

## 第一步 — 生态基底（GenerateDungeonEcologySystem）

**触发**：`GenerateDungeonAction`

一次 LLM 调用决定地下城的三个基本属性：名称（格式 `地下城.XXXX`）、生态环境描述、以及场景数量（2 或 3，由 LLM 根据地形规模判断）。生态描述刻意回避生物名称与威胁语气，只呈现感官环境，作为下游步骤的世界观底色。

产物 `DungeonEcologyData` 传递给第二步，场景数量在此处被"锁定"，后续步骤严格遵循。

---

## 第二步 — 场景设计（GenerateDungeonStagesSystem）

**触发**：`GenerateDungeonStagesAction`，读取 `DungeonEcologyData`

**为何一次性生成所有场景**：保证场景间叙事连贯——同一个 LLM 上下文内生成，可以自然形成从入口（稀疏、开放）到深处（浓密、压迫）的深度递进感。如果分多次调用，各场景之间容易缺乏呼应。

每个场景的决策包含：名称（格式 `场景.XXXX`）、档案标识、环境描述、以及该场景内的角色数量（`actor_count`，1 或 2）。入口场景倾向于 1 个角色，深处场景可以是 2 个。

产物 `DungeonStagesData` 包含所有场景的结构，其中各场景的角色数量是第三步并发扩展的依据。

---

## 第三步 — 角色生成（GenerateDungeonActorsSystem）

**触发**：`GenerateDungeonActorsAction`，读取 `DungeonStagesData`

**核心设计：并发批量调用**。系统将所有 `(场景, 角色序号)` 对展开为一组 `DeepSeekClient` 实例，通过 `DeepSeekClient.batch_chat()` 并发执行，总调用数 = 各场景 `actor_count` 之和。并发而非串行的选择纯粹出于性能考量——角色之间无依赖关系。

对于同一场景内的多个角色，提示词会告知 LLM 当前是"第 X 个，共 Y 个"，引导它生成形态、策略有所差异的生物，避免重复。

角色的两段描述分工明确：`profile` 是第一人称的行为意图与性格（AI 驱动用），`base_body` 是第三人称的外形描述（渲染或插图用）。

所有结果聚合为 `DungeonBlueprint`，结构为地下城 → 场景列表 → 每场景的角色列表。单个角色 LLM 调用失败时只丢弃该角色；所有角色均失败才丢弃整个场景。

---

## 第四步 — 实体组装（AssembleDungeonSystem）

**触发**：`AssembleDungeonAction`，读取 `DungeonBlueprint`

本步骤不调用 LLM，是纯确定性的数据转换：将蓝图中的平面 JSON 结构转化为 ECS 实体树（`Dungeon` → `CombatRoom` 列表 → 每个 `CombatRoom` 含一个 Stage 及其 Actor 列表）。

Actor 创建时注入统一的战斗规则关键字（卡牌攻击导向描述），这是 RPG 系统规则对生成物的唯一强制约束。

**兜底去重**：极端情况下 LLM 可能为不同场景或角色生成相同名称。组装时分别对 stage 名称与 actor 名称维护已用名称集合，重复时追加数字后缀（`_2`、`_3`），并记录警告日志，正常流程不触发。

最终产物 `Dungeon` 序列化写入 `DUNGEONS_DIR`，同时将蓝图副本写入 `DEBUG_CACHE_DIR` 供调试比对。此时蓝图中的图片 URL 字段（地下城封面与各场景插画）均为空，留待第五步填充。

---

## 第五步 — 场景插画（IllustrateDungeonActionSystem）

**触发**：`IllustrateDungeonAction`

本步骤调用图像生成模型，为地下城产出两类视觉材料：**每个战斗场景各生成一张环境插画**，以及**地下城整体生成一张封面图**。两类图片 URL 分别写回对应的蓝图数据结构，供前端展示与沉浸式体验使用。

图片生成被设计为最后一步，原因有二：其一，图片仅以前三步产出的文字描述作为输入，与 ECS 实体结构无关，无需等待组装完成；其二，与文本生成步骤解耦后，单张图片请求失败不会阻断地下城的可用性——前四步的产物（完整的 ECS 实体树）已可投入游戏流程。

---

## 设计决策小结

| 决策 | 理由 |
| --- | --- |
| 场景数量由 LLM 决定（2–3） | 不同地形规模应有不同深度感，硬编码会导致生成物单一 |
| 每场景角色数由 LLM 决定（1–2） | 入口与深处的威胁密度不同，由 LLM 结合场景剧情判断更自然 |
| 第二步一次性生成所有场景 | 保证场景间的叙事连贯性与递进感 |
| 第三步并发批量调用 | 角色间无依赖，并发可将总耗时压缩至最长单次调用的时间 |
| 中间文件落盘 | 任一步骤失败可从上一步的 JSON 文件恢复，无需重跑全链路 |
| 第四步零 LLM 调用 | 组装是纯结构映射，不需要创意决策，避免引入不必要的随机性 |
| 图片生成置于最后（第五步） | 图片仅需文字描述输入，与 ECS 实体结构无关；解耦后单次图片失败不阻断地下城可用性 |
| 场景图与封面图分别存储 | 场景图服务于战斗沉浸感，封面图服务于地下城入口展示，两者用途与更新时机不同 |
