# 神器（Artifact）

---

## 定位

神器是内容作者书写的**场景级战斗修正规则**载体，与 `Card` 同级：它是一个独立的战斗价值模型，不是实体、不进背包、不属于道具流（不是 `Item`/`AnyItem` 的子类），也不物化为卡牌。

## 构成

`Artifact` 定义在 `src/ai_rpg/models/artifact.py`：

| 字段 | 说明 |
| --- | --- |
| `name` | 神器全名（如 `神器.兽骨图腾`） |
| `description` | 叙事锚点：神器的意象与来历，不含数值 |
| `source` | 来源/归属实体：标识该神器以谁的名义生效；空字符串表示未知 |
| `modifiers` | 修正规则（多值）：每个元素是一条完整、独立的规则，由仲裁者逐条全部结算 |
| `phases` | 生效运行点，`List[ArtifactPhase]`，默认 `[POST_ARBITRATION]` |
| `uuid` | 全局唯一标识符 |

`ArtifactPhase` 是运行点枚举，目前只有 `POST_ARBITRATION`（出牌仲裁之后）。新增运行点时，定义新的枚举值并由对应仲裁系统按 `phases` 过滤自己所负责的神器。

## 挂载

归属由 `ReliquaryComponent` 声明：Actor / Stage 均可携带该组件，列出其名下神器。`ArtifactPostArbitrationSystem` 结算当前战斗舞台（stage）与场上存活角色携带的神器；`source` 指定该神器以谁的名义生效（未指定时以携带者为归属），而仲裁者始终是 stage。

## 仲裁时如何生效

出牌仲裁由场景实体先完成一次结算。随后 `ArtifactPostArbitrationSystem` 响应 `PlayCardsAction`：

1. 由动作实体定位当前战斗舞台（stage），汇集该 stage 与场上存活角色 `ReliquaryComponent` 中 `phases` 命中 `POST_ARBITRATION` 的神器（按 uuid 去重）；无则跳过。
2. 以 **stage 实体为仲裁者**（与出牌、回合结束仲裁一致）：提示词注入当前回合数、场上存活阵营，以及每个神器的 `description`、`source`（未指定时取携带者）与 `modifiers`；工具面为 `get_entity_stats` / `set_entity_hp` / `submit_arbitration`。
3. 仲裁者依规则判定是否触发并调用 `set_entity_hp` 覆盖式写入最终 HP，提交战斗日志/叙事；结果写入 stage 记忆、广播给场上角色，并向本回合记录队列追加一条 `RoundEntryKind.ARTIFACT` 记录。

> 记忆去向：仲裁者是所在场景，每次结算（prompt、工具轨迹、结果）写入 **stage 持久记忆**；场景与场上角色通过广播获得「发生了什么」。

> 触发状态：神器不再拥有自身记忆。「一次性效果是否已触发」由 stage 在本场战斗中的记忆判断——这与出牌/回合结束仲裁完全一致，无需为神器维护独立上下文。

> 权限边界：神器仲裁不读也不写场景环境快照（`EnvironmentComponent`）。它对环境的认知只来自被广播与写入记忆的事件，由后续推理自行维护。

## 设计意图

- 机制与内容分离：场景规则是数据，不是硬编码进仲裁系统的分支；运行点用 `ArtifactPhase` 表达，可扩展。
- 仲裁者归一：神器、出牌、回合结束三者均由 stage 仲裁，共享同一套工具面、记忆与广播路径。
- 借重 LLM 的灵活性：规则由 stage 在运行时按需解释，而非系统预先筛选注入，保留内容表达的空间。
- 场景级而非卡牌级：神器规则对该场景内所有出牌仲裁生效，是背景约束；卡牌词缀则属于单次出牌/受击结算。

→ 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)（出牌仲裁与各仲裁者的归属）
→ 参见：[卡牌数据模型（Card）](card.md)（卡牌词缀的单次结算语义）
