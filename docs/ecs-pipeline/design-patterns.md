# ECS 管线设计模式

> 本文档描述所有管线共同遵循的四种架构约定。  
> 上级入口：[[overview]]

---

## 1. 首尾夹持（Bookend Pattern）

每条管线的 **第一个** System 必须是 `PrologueSystem`，**最后一个** 必须是 `EpilogueSystem`。

```text
PrologueSystem          ← 入口占位符，未来可扩展前置检查
  ...业务 Systems...
ActionCleanupSystem     ← 清理 Action 组件
DestroyEntitySystem     ← 销毁标记实体
EpilogueSystem          ← flush 状态 + 记录日志
```

这两个 System 的详细说明见 [[systems-shared]]。

**意义**：无论管线中有多少业务 System，生命周期边界始终清晰，收尾操作不会被遗漏。

---

## 2. Action 驱动的单帧消费模式

游戏输入（玩家操作 / AI 决策）通过向 Entity 添加 **Action Component** 传入，遵循严格的单帧消费语义：

```text
[输入]  Entity 被挂上 XxxAction Component
   ↓
[处理]  ReactiveProcessor 监听 GroupEvent.ADDED，触发 react()
   ↓
[清理]  ActionCleanupSystem 统一移除所有 Action Component
   ↓
[下一帧输入准备完毕]
```

所有 `ReactiveProcessor` 类型的 System 均基于此模式运作。Action Component 不会跨帧残留，保证幂等性。

**注意**：`ActionCleanupSystem` 清理的是 `ACTION_COMPONENT_TYPES` 注册表中的所有类型，新增 Action 类型时需要在注册表中同步声明。

---

## 3. 状态守卫（State Guard）

部分 System 虽然出现在多条管线中，但内部会主动检查当前游戏阶段，不符合条件则 **提前返回**，不执行实际逻辑。

典型案例：

| System | 守卫条件 |
| -------- | ---------- |
| `StageDescriptionSystem` | 只在场景描述组件为空（尚未生成）时触发 LLM 推理 |
| `CombatArchiveSystem` | 只在战斗刚结束（`CombatArchiveEvent` 存在）时触发归档 |
| `CombatInitializationSystem` | 只在战斗开始阶段（无回合记录）时创建第一回合 |
| `CombatRoundTransitionSystem` | 只在旧回合已清理、战斗仍在进行时创建新回合 |

**意义**：同一个 System 实例可以安全地接入多条管线，无需为不同场景编写分支管线。

---

## 4. 并行 LLM 推理

当一帧内需要为**多个 Entity 同时调用 LLM** 时，系统通过 `ChatClient.batch_chat` 批量并行发出请求，等待全部响应后再统一写回组件。

```python
# 伪代码示意
requests = [build_request(entity) for entity in entities]
responses = await chat_client.batch_chat(requests)   # 并行
for entity, response in zip(entities, responses):
    entity.replace(SomeComponent, parse(response))
```

涉及此模式的 System：`ActorAppearanceUpdateSystem`、`StageDescriptionSystem`、`HomeActorSystem`、`DrawCardsActionSystem`。

**意义**：避免 N 个角色串行等待 LLM，将延迟从 O(N) 降至近似 O(1)。
