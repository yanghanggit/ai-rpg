# 家园规划系统（Home Plan Action）

## 定位

家园模式下把「本轮谁行动」转化为 ECS 行动组件的响应式系统对。`HomeNpcPlanSystem` 处理 NPC——自主决策、真实调用 LLM；`HomePlayerPlanSystem` 处理玩家——动作已由客户端决定、不调用 LLM。二者共享同一触发信号 `PlanAction`，按阵营分流后殊途同归：把决策落成 `SpeakAction` 等组件交给下游动作系统。

## 设计决策

### 触发信号与阵营分流

`PlanAction` 不携带行动内容，只标记「该角色本轮应产出行动」。挂载方决定谁行动：玩家侧由家园动作服务在挂载动作组件时一并挂载；NPC 侧由 `advance` 命令显式点名。两个系统监听同一 `ADDED` 事件，靠阵营组件分流——玩家角色同时持有 `NPCComponent` 与 `PlayerComponent`，NPC 系统以「非玩家」为条件排除之，避免对同一实体重复触发。

### 工具调用式规划

NPC 规划从「一次性输出 JSON」改为 agentic 循环工具调用，两个工具把行动约束结构化：

- `query_knowledge_base`（非终止）：检索公共知识库，结果回流本轮，可多次调用。
- `submit_action_plan`（终止）：提交最终行动决策，调用即结束循环。

互斥关系由工具 schema 天然承载：`mind` 必填且独立；`speak` / `whisper` / `announce` 三选一；`trans_stage` 与前三者互斥；`none` 表示仅内心独白。`query` 可与任意行动叠加，且只能发生在提交之前——「先查后决策」是相对旧方案（检索结果下一轮才可见）的关键差异。

### 收集与落库分离

工具 handler 只把参数收集进结果容器，不产生副作用；循环结束后按实体顺序串行落库。分离的意图：LLM 决策可并发（多个角色同时思考），落库必须串行以保证事件顺序确定、副作用可控。

### 记忆「什么就是什么」

NPC 的循环原地写入持久记忆，真实工具调用轨迹（工具调用 + 工具消息）即记忆本身，不事后改写。玩家侧伪造一条等价的 `submit_action_plan` 轨迹——相同的规划提示、带工具调用的 AI 消息、工具消息——使玩家与 NPC 的记忆结构一致，后续 LLM 消费时无需区分来源。这取代了旧的「影子 plan」。

## 跨系统关联

- 上游：家园动作服务挂载 `PlanAction` 与玩家动作组件 → 参见：[AI 操作 CLI（run_agent_game.py）](run-agent-game.md)
- 下游：`SpeakAction` / `WhisperAction` / `AnnounceAction` / `TransStageAction` 由对应动作系统消费并广播；`ActionCleanupSystem` 每帧清理动作组件
- `query_knowledge_base` 复用公共知识检索，替代原 `QueryAction` 组件链路 → 参见：[公共知识检索系统（RAG）](rag-knowledge-base.md)
