# 战役设定与全局规则桥接（CAMPAIGN_SETTING / RPG_SYSTEM_RULES）

## 分层

世界知识分两层注入每个实体的 system prompt，以机制与内容解耦：

- `RPG_SYSTEM_RULES`：跨故事固化的引擎规则（角色扮演契约、副本定义、场景移动、战斗机制），保持不动。
- `CAMPAIGN_SETTING`：仅目标故事生效的动态设定（时代锚点、类型标签、副本的梦境语义），是全部实体的最低公共知识。

故事语义只进 `CAMPAIGN_SETTING`，不进 `RPG_SYSTEM_RULES`。

## 抽象设定是惰性知识

仅写进设定层的故事语义，不足以让 LLM 在事件时刻稳定体现——LLM 就近采信事件通知文案，不会自发回读 system prompt 中远置的抽象设定（触发缺口）。

## 事件级引用提示

在副本生命周期通知（进入 / 推进 / 退出 / 撤退）中追加一句通用引用，把事件时刻的 LLM 指回自身 system prompt：关于副本及进出副本的设定，见你的「游戏设定」与「全局规则」。

该句不含故事专属内容，语义仍只存于 `CAMPAIGN_SETTING`，通知只负责触发回读。通知文案保持通用，引擎代码不被具体故事语义污染。

## 关联

- 副本=梦境的故事语义来源。→ 参见：[新故事设计：《大渊》](新故事设计.md)
- 副本概念的生成与实体化。→ 参见：[副本生成管道（Dungeon Generation Pipeline）](dungeon-generation.md)
