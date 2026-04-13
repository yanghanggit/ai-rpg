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
| 4 | `HomeActorSystem` | Execute | **核心**：NPC/Actor AI 规划行动 |
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

### HomeActorSystem（步骤 4）

**源码**：`src/ai_rpg/systems/home_actor_system.py`  
**类型**：`ReactiveProcessor`（监听 `MindEvent` 等触发条件）

这是家园管线的"大脑"，负责驱动所有 NPC 和响应玩家意图。

**AI 规划输出格式**（`ActionPlanResponse`）：

```text
mind        内心独白（不对外可见）
query       向量数据库检索关键词 → 触发 QueryAction
speak       说话目标 → 内容映射 → 触发 SpeakAction
whisper     耳语目标 → 内容映射 → 触发 WhisperAction
announce    公开宣布内容 → 触发 AnnounceAction
trans_stage 移动目标场景名 → 触发 TransStageAction
```

**玩家主动行动守卫**：若本帧玩家已持有 `SpeakAction` / `WhisperAction` / `AnnounceAction` / `TransStageAction` 中的任意一种，NPC 进入待命模式，不触发 AI 规划，避免玩家与 NPC 同帧竞争。

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
