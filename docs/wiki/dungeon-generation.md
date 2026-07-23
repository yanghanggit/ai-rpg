# 地下城生成流程（Dungeon Generation Pipeline）

地下城生成由 `ReactiveProcessor` 接力驱动，每步通过添加 Action 组件触发下一步，中间产物落盘为 JSON 便于调试与回溯。设计原则：**前三步 LLM 创作文本，第四步纯数据组装，第五步（插画）当前未接入主流程**。

---

## 流水线现状

`create_dungeon_generate_pipeline` 目前只注册 Step 1–4（生态 → 场景 → 角色 → 组装）。`IllustrateDungeonActionSystem`（Step 5，插画）代码已实现，但其 import 与 `processors.add` 在该工厂函数中均被注释掉，未接入这条 pipeline——地下城生成完成后不会自动产出插画，`Dungeon`/场景数据中的图片 URL 字段会持续为空。

中间文件写入 `DUNGEON_PROCESS_DIR`，命名 `{地下城名}_step{N}_*.json`；成品写入 `DUNGEONS_DIR`。

---

## Step 1 — 生态基底（GenerateDungeonEcologySystem）

一次 LLM 调用确定地下城名称、生态描述与场景数量（枚举 2/3，依地形规模判断），场景数量在此"锁定"，后续步骤严格遵循。生态描述刻意回避生物名称与威胁语气，只呈现感官环境。

## Step 2 — 场景设计（GenerateDungeonStagesSystem）

一次 LLM 调用生成全部场景（名称、`profile`、`actor_count`，枚举 1/2）。**为何一次性生成**：同一上下文内产出才能形成入口到深处的叙事递进与呼应，分次调用容易脱节。

## Step 3 — 角色生成（GenerateDungeonActorsSystem）

将所有 `(场景, 角色序号)` 对展开为并发 `DeepSeekClient.batch_chat()` 调用——角色间无依赖，纯性能考量。提示词告知 LLM"当前第几个/共几个"以避免形态重复。`profile`（第一人称行为意图，AI 驱动用）与 `base_body`（第三人称外形，渲染用）职责分离。单角色失败只丢弃该角色，全场角色均失败才丢弃场景。

## Step 4 — 实体组装（AssembleDungeonSystem）

零 LLM 调用，纯确定性转换：`DungeonBlueprint` → ECS 实体树（`Dungeon` → `CombatRoom` 列表 → Stage + Actor）。重名兜底：stage/actor 名称冲突时追加 `_2`/`_3` 后缀并记录警告，正常流程不触发。图片 URL 字段留空，供 Step 5（若被触发）填充。

## Step 5 — 场景插画（IllustrateDungeonActionSystem，未接入主流程）

调用图像模型为每个战斗场景生成环境插画，并为地下城生成一张封面图。设计上独立于 ECS 结构、单张失败不阻断可用性；但当前未被 `create_dungeon_generate_pipeline` 注册，若需启用需由外部脚本单独驱动。

---

## 设计决策小结

| 决策 | 理由 |
| --- | --- |
| 场景数量、每场景角色数均由 LLM 决定 | 硬编码会导致不同地形规模/深度层次的生成物单一 |
| Step 2 一次性生成所有场景 | 保证场景间的叙事连贯性与递进感 |
| Step 3 并发批量调用 | 角色间无依赖，并发可将总耗时压缩至最长单次调用的时间 |
| 中间文件落盘 | 任一步骤失败可从上一步的 JSON 文件恢复，无需重跑全链路 |
| Step 4 零 LLM 调用 | 组装是纯结构映射，不需要创意决策，避免引入不必要的随机性 |
| Step 5 与主 pipeline 解耦 | 图片仅需文字描述输入，与 ECS 实体结构无关；未接入意味着可独立按需触发，不阻塞地下城基础可用性 |
