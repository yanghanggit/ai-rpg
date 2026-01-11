# AgentContext 消息管理机制

## 核心概念

`AgentContext` 是游戏中每个实体（角色、场景、世界系统）的 **LLM 对话上下文容器**，存储该实体与 LLM 交互的完整历史记录。

```python
class AgentContext(BaseModel):
    name: str  # 实体名称
    context: List[SystemMessage | HumanMessage | AIMessage]  # 消息历史
```

**存储位置**：`World.agents_context: Dict[str, AgentContext]`

---

## 消息结构规则

### 标准对话流

```text
[0] SystemMessage    ← 角色身份/规则（固定第一条，永不改变）
[1] HumanMessage     ← 游戏指令/事件
[2] AIMessage        ← LLM 响应
[3] HumanMessage     ← 游戏通知（可连续多条）
[4] HumanMessage     ← 游戏通知
[5] AIMessage        ← LLM 响应
...
```

**关键特征**：

- ✅ **SystemMessage 必须是第一条消息**（初始化时添加）
- ✅ **HumanMessage 可以连续出现**（游戏事件累积）
- ✅ **AIMessage 只在 LLM 调用后添加**（决策响应）

---

## 三大核心方法

### 1. `add_system_message(entity, message_content)`

**用途**：初始化实体的系统提示词（角色设定、游戏规则）

**约束**：

- 只能在 `context` 为空时调用
- 每个实体只能有一条 SystemMessage
- 包含角色身份、性格、历史、游戏规则等

**调用时机**：

```python
# 创建角色实体时
self._create_actor_entities(actors)
  └─> self.add_system_message(actor_entity, actor_model.system_message)
```

---

### 2. `add_human_message(entity, message_content, **kwargs)`

**用途**：添加游戏事件、指令、通知到实体上下文

**关键特性 - kwargs 标记系统**：

```python
# 战斗开始标记
self._game.add_human_message(
    actor_entity,
    "# 通知！战斗触发！...",
    combat_kickoff="场景.训练场"  # 👈 自定义属性
)

# 游戏启动标记
self._game.add_human_message(
    actor_entity,
    "# 游戏启动！...",
    kickoff="角色.战士.卡恩"
)

# 压缩提示词标记
self._game.add_human_message(
    actor_entity,
    "# 指令！第1回合...",
    compressed_prompt="..."  # 实际发送给 LLM 的简化版
)
```

**kwargs 用途**：

- 🏷️ 标记特殊消息（战斗开始/结束、场景转换等）
- 🔍 便于后续检索（`filter_human_messages_by_attribute`）
- 🗑️ 支持精确删除（消息压缩时使用）

---

### 3. `add_ai_message(entity, ai_messages: List[AIMessage])`

**用途**：添加 LLM 的响应消息

**包含元数据**：

```python
AIMessage(
    content="（将磨刀石放在脚边，缓缓站起）我是角色.战士.卡恩...",
    response_metadata={
        "token_usage": {...},
        "model_provider": "deepseek",
        "model_name": "deepseek-chat",
        "prompt_cache_hit_tokens": 768  # 缓存命中，节省成本
    }
)
```

**调用时机**：

```python
# LLM 调用后立即添加
chat_client = ChatClient(...)
await chat_client.request_post()
self._game.add_ai_message(entity, chat_client.response_ai_messages)
```

---

## 高级功能：消息检索与压缩

### 检索带标记的消息

```python
# 查找所有战斗开始消息
begin_messages = self._game.filter_human_messages_by_attribute(
    actor_entity=entity,
    attribute_key="combat_kickoff",
    attribute_value="场景.训练场"
)
```

### 压缩战斗历史

```python
# 删除战斗开始到结束之间的详细消息，替换为摘要
deleted_messages = self._game.remove_message_range(
    entity,
    begin_message=begin_messages[0],  # 战斗开始标记
    end_message=end_messages[0]        # 战斗结束标记
)
```

**压缩原因**：

- 🎯 控制 token 数量，避免超出 LLM 上下文限制
- 💰 减少 API 调用成本
- ⚡ 保留战斗结果摘要，丢弃详细过程

---

## 广播模式

### `broadcast_to_stage(entity, agent_event, exclude_entities)`

**功能**：向场景内所有存活角色 + 场景实体广播事件

**调用链**：

```text
broadcast_to_stage
  └─> notify_entities(need_broadcast_entities, agent_event)
        └─> add_human_message(entity, agent_event.message)  # 每个实体
        └─> player_session.add_agent_event_message()        # 发送到客户端
```

**示例**：

```python
# 角色对话广播
self._game.broadcast_to_stage(
    entity=speaker,
    agent_event=SpeakEvent(message="...", actor="...", target="..."),
    exclude_entities={speaker}  # 排除发言者自己
)
```

---

## 实际调用路径示例

### 示例 1：战斗初始化

```text
combat_initialization_system.py
  └─> add_human_message(actor_entity, combat_kickoff_prompt, combat_kickoff=stage_name)
  └─> add_ai_message(actor_entity, [AIMessage("我准备好了，等待战斗开始！")])
```

### 示例 2：卡牌生成

```text
draw_cards_action_system.py
  └─> add_human_message(entity, "# 指令！第1回合...", compressed_prompt="...")
  └─> ChatClient.gather_request_post()  # LLM 调用
  └─> add_ai_message(entity, chat_client.response_ai_messages)
```

### 示例 3：战斗后处理

```text
combat_post_processing_system.py
  └─> filter_human_messages_by_attribute(entity, "combat_kickoff", stage_name)
  └─> filter_human_messages_by_attribute(entity, "combat_outcome", stage_name)
  └─> remove_message_range(entity, begin_msg, end_msg)  # 压缩历史
```

---

## 关键设计模式

### 1. **消息标记系统**

通过 kwargs 给 HumanMessage 添加自定义属性，实现消息的精确检索和删除。

### 2. **上下文隔离**

每个实体独立维护自己的 context，互不干扰，支持并行处理。

### 3. **渐进式上下文积累**

游戏事件通过连续的 HumanMessage 累积，影响 AI 的下一次决策。

### 4. **消息压缩机制**

通过标记找到特定消息范围，删除详细过程，替换为 AI 生成的摘要。

---

## 数据存储格式

### JSON 格式（可序列化）

```json
{
  "name": "角色.战士.卡恩",
  "context": [
    {"type": "system", "content": "..."},
    {"type": "human", "content": "...", "kickoff": "角色.战士.卡恩"},
    {"type": "ai", "content": "...", "response_metadata": {...}}
  ]
}
```

### Buffer 格式（人类可读）

```text
System: # 角色.战士.卡恩 ...
H: # 游戏启动！...
AI(角色.战士.卡恩): 我是角色.战士.卡恩。...
H: # 通知！外观更新...
```

---

## 快速参考

| 方法 | 用途 | 约束 | kwargs 支持 |
| ------ | ------ | ------ | ------------- |
| `add_system_message` | 初始化身份 | 只能第一条 | ❌ |
| `add_human_message` | 添加游戏事件 | 无限制 | ✅ |
| `add_ai_message` | 添加 LLM 响应 | 需要 List[AIMessage] | ❌ |

| 辅助方法 | 用途 |
| --------- | ------ |
| `filter_human_messages_by_attribute` | 根据 kwargs 检索消息 |
| `remove_human_messages` | 删除指定消息列表 |
| `remove_message_range` | 删除消息范围（用于压缩） |
| `broadcast_to_stage` | 向场景内所有实体广播 |
| `notify_entities` | 向指定实体集合发送通知 |

---

## 最佳实践

✅ **DO**：

- 使用 kwargs 标记重要的游戏事件（战斗、场景转换等）
- 定期压缩历史消息，控制 token 数量
- 为每个实体维护独立的 context，避免信息泄露

❌ **DON'T**：

- 不要在非空 context 中添加 SystemMessage
- 不要在 SystemMessage 中包含易变的游戏状态
- 不要忘记在战斗结束后压缩历史记录
