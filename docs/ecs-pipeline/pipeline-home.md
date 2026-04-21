# 家园管线（Home Pipeline）

> 工厂函数：`create_home_pipeline`  
> 源码：`src/ai_rpg/game/tcg_game_process_pipeline.py`  
> 上级入口：[[overview]]

---

## 适用场景

玩家与 NPC 处于**家园场景**时，每一帧触发此管线。  
家园是非战斗的自由交互区域：NPC 自主行动、玩家发令、角色移动场景等均在此管线中完成。

---

## 执行顺序

| 步骤 | System | 类型 | 职责 |
| ------ | -------- | ------ | ------ |
| 1 | `PrologueSystem` | Execute | 管线入口 → [[systems-shared#PrologueSystem]] |
| 2 | `ActorAppearanceUpdateSystem` | Execute | 生成角色外观描述 → [[systems-shared#ActorAppearanceUpdateSystem]] |
| 3 | `StageDescriptionSystem` | Execute | 生成场景环境描述 → [[systems-shared#StageDescriptionSystem]] |
| 4 | `HomeActorPlanSystem` | Execute | **核心**：NPC/Actor AI 规划行动 |
| 5 | `QueryActionSystem` | Reactive | 执行 RAG 向量检索 |
| 6 | `PlayerActionAuditSystem` | Reactive | 审核玩家行动合法性 |
| 7 | `SpeakActionSystem` | Reactive | 处理说话行动 |
| 8 | `WhisperActionSystem` | Reactive | 处理耳语行动 |
| 9 | `AnnounceActionSystem` | Reactive | 处理公告行动 |
| 10 | `TransStageActionSystem` | Reactive | 处理场景转移 |
| 11 | `ActionCleanupSystem` | Execute | 清理所有 Action → [[systems-shared#ActionCleanupSystem]] |
| 12 | `DestroyEntitySystem` | Execute | 销毁标记实体 → [[systems-shared#DestroyEntitySystem]] |
| 13 | `EpilogueSystem` | Execute | flush 状态 → [[systems-shared#EpilogueSystem]] |

---

## 核心系统详解

### HomeActorPlanSystem（步骤 4）

**源码**：`src/ai_rpg/systems/home_actor_plan_system.py`

家园管线的"大脑"。每帧为 NPC 调用 LLM 规划行动，同时为玩家注入场景观察上下文（不调 LLM）。AI 以结构化 JSON 输出决策，涵盖内心独白、信息查询、对外交流、装备操作与场景移动五类意图，由后续 Reactive System 逐类消费。

**规划回合计数**：计数器持久化于 `World`，每帧自增后注入所有角色的提示词。存档恢复后可从正确编号续接，为 AI 提供连贯的时间感知。

**Prompt 压缩**（`use_compressed_prompt`，默认开启）：对话历史只写入每轮变化的动态感知部分（场景叙述、可移动列表、其他角色外观），大幅减少重复 token 占用。静态规则与格式说明以 `home_actor_full_prompt` 附挂在消息额外字段中保留，LLM 推理仍使用完整版。

**玩家主动行动守卫**：玩家本帧已提交主动行动时，NPC 跳过 LLM 推理进入待命，防止玩家与 NPC 同帧竞争资源。

参见 [[design-patterns#4. 并行 LLM 推理]]

---

### QueryActionSystem（步骤 5）

**源码**：`src/ai_rpg/systems/query_action_system.py`  
**监听**：`QueryAction` Component 被添加（`GroupEvent.ADDED`）

执行 RAG 检索：用角色提出的问题查询 ChromaDB 向量数据库，将检索结果注入角色上下文（`add_human_message`）。若无结果则注入"无相关信息"提示，避免角色对同一问题重复查询。

---

### PlayerActionAuditSystem（步骤 6）

**源码**：`src/ai_rpg/systems/player_action_audit_system.py`  
**类型**：`ReactiveProcessor`

对玩家提交的行动进行合法性审核，过滤不符合当前游戏规则或场景约束的输入，防止玩家绕过游戏逻辑。

---

### 行动处理系统（步骤 7-10）

均为 `ReactiveProcessor`，监听对应 Action Component 被添加后触发：

| System | 监听 Component | 核心行为 |
| -------- | --------------- | ---------- |
| `SpeakActionSystem` | `SpeakAction` | 将发言内容广播给目标角色的消息上下文 |
| `WhisperActionSystem` | `WhisperAction` | 仅向指定目标注入私信内容 |
| `AnnounceActionSystem` | `AnnounceAction` | 向场景内所有角色广播公告 |
| `TransStageActionSystem` | `TransStageAction` | 更新角色所在场景，触发场景切换逻辑 |

参见 [[design-patterns#2. Action 驱动的单帧消费模式]]
