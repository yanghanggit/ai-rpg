# 战役设定与全局规则（CAMPAIGN_SETTING / SYSTEM_RULES）

## 分层

世界知识分两层注入每个实体的 system prompt，二者都封存在 `demo/`（故事层），引擎保持内容无关：

- `SYSTEM_RULES`：全局规则（角色扮演契约、游戏实体、实体全名、根属性、战斗机制、场景移动、扮演与事实）。副本=梦境的语义直接写在本层——进入副本即进入梦境、进出副本即入梦与醒来。
- `CAMPAIGN_SETTING`：战役大背景（时代锚点、类型标签、寻常/诡谲双层面、核心玩法），是全部实体的最低公共知识。

`Blueprint` 以 `campaign_setting` 与 `system_rules` 两个字段承载这两个 prompt 层字段；工厂（create_actor / create_stage / create_world）与副本组装系统（AssembleDungeonSystem）都从蓝图取值，不再硬编码任何规则文本。

## 故事层两字段（Blueprint）

`Blueprint` 是引擎与故事之间唯一的注入边界，共承载两个故事层字段；引擎只按字段消费，不含任何具体故事文本。

| 字段 | 故事常量（demo/world.py） | 消费方 | 注入目标 |
| --- | --- | --- | --- |
| `campaign_setting` | `CAMPAIGN_SETTING` | 工厂（create_actor / create_stage / create_world）、AssembleDungeonSystem | 实体 system prompt 的「游戏设定」段 |
| `system_rules` | `SYSTEM_RULES` | 同上 | 实体 system prompt 的「全局规则」段 |

字段默认值均为空串，旧 Blueprint / 存档未涉及引擎不认识的字段。

## 插图风格由世界实体承载

副本插图的画风、构图与负面词**不再进入 Blueprint**，而是由 `world_entities` 中的「世界.插图提示词」实体（`IllustrationPromptComponent`）承载：其 `role_rules`（system prompt）定义视觉方向与提示词写作要求，Step 5 由该实体作为 agent 为封面与各房间编排文生图提示词。

引擎（IllustrateDungeonActionSystem）只传递事实（副本 / 场景 / 生物设定）与调用图像模型，不含任何具体画风或构图模板。换故事只改 `demo/world.py` 的该世界实体。

## 抽象设定是惰性知识

写进 system prompt 的故事语义属于惰性知识——LLM 就近采信事件通知文案，不会自发回读 system prompt 中远置的抽象设定（触发缺口）。

## 事件级引用提示

在副本生命周期通知（进入 / 推进 / 退出 / 撤退）中追加一句通用引用，把事件时刻的 LLM 指回自身 system prompt：关于副本及进出副本的设定，见你的「游戏设定」与「全局规则」。

该句不含故事专属内容，语义只存于 `SYSTEM_RULES` 与 `CAMPAIGN_SETTING`（均在 demo/），通知只负责触发回读。通知文案保持通用，引擎代码不被具体故事语义污染。

## 关联

- 副本=梦境的故事语义来源。→ 参见：[新故事设计草稿：《大渊》](新故事设计草稿.md)
- 副本概念的生成与实体化。→ 参见：[副本生成管道（Dungeon Generation Pipeline）](dungeon-generation.md)
- 插图风格字段的消费方。→ 参见：[副本插图生成系统（Step 5）](../../src/ai_rpg/systems/illustrate_dungeon_action_system.py)