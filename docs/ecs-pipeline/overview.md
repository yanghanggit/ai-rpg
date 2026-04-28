# ECS 管线设计 — 总览

> 本领域文档描述 ai-rpg 游戏框架中"流程管线（Pipeline）"的整体架构。  
> 上级入口：[[../README]]

---

## 什么是管线

游戏每一帧（`pipeline.process()`）的执行单元是 **`RPGGameProcessPipeline`**，它封装一组有序的 `System`，依次执行后完成一轮游戏逻辑。

```text
pipeline.process()
    └─ execute_all()   → 按顺序调用每个 System.execute()
    └─ cleanup_all()   → 按顺序调用每个 CleanupProcessor.cleanup()
```

`RPGGamePipelineManager` 负责注册和管理所有管线的生命周期（初始化 / 关闭）。

---

## 三条管线与触发时机

| 管线 | 工厂函数 | 触发场景 | 详细文档 |
| ------ | ---------- | ---------- | ---------- |
| 家园管线 | `create_home_pipeline` | 玩家与 NPC 处于家园场景时 | [[pipeline-home]] |
| 战斗管线 | `create_combat_pipeline` | 玩家进入地牢、战斗进行中 | [[pipeline-combat]] |
| 地牢生成管线 | `create_dungeon_generate_pipeline` | 离线/按需生成新地牢内容 | [[pipeline-dungeon-generate]] |

三条管线均在 `TCGGame.__init__` 中创建并注册，整个游戏生命周期内只创建一次。

---

## TCGGame 实体初始化

管线之外，`TCGGame` 在两个关键时机执行**一次性组件挂载**，将蓝图数据注入 ECS 实体：

| 调用点 | 挂载的实体 | 挂载的组件 |
| -------- | ---------- | ---------- |
| `build_from_blueprint()` | 家园角色（玩家 + 盟友） | `DrawDeckComponent` / `DiscardDeckComponent` / `KeywordComponent` |
| `setup_dungeon_entities()` | 地下城怪物（新创建后） | `DrawDeckComponent` / `DiscardDeckComponent` / `KeywordComponent` |

函数命名规范：前缀 `_mount_`（非 `_ensure_`），明确表达"与实体创建流程强绑定、不允许重复调用"的一次性语义。

- `_mount_actor_deck_components()` — 为所有尚无牌组组件的 Actor 实体同时挂载空 `DrawDeckComponent`（可重抽历史牌池）和 `DiscardDeckComponent`（已打出卡牌归档）
- `_mount_actor_keyword_components()` — 从蔗图 `Actor.keywords` 读取约束，挂载 `KeywordComponent`

`KeywordComponent` 详细设计见：[[keyword-system]]

---

## System 基类类型

| 基类 | 执行时机 | 典型用途 |
| ------ | ---------- | ---------- |
| `InitializeProcessor` | 管线初始化时执行一次 | 加载资源、订阅事件 |
| `ExecuteProcessor` | 每帧无条件执行 | 主动检查、定期处理 |
| `ReactiveProcessor` | 监听到指定 Component 被添加时触发 | 响应玩家/AI 的 Action |
| `CleanupProcessor` | 每帧 execute 结束后执行 | 清理临时状态 |
| `TearDownProcessor` | 管线关闭时执行一次 | 释放资源 |

---

## 共享系统

多条管线复用的系统，统一在此文档说明，各管线文档不重复描述：

→ [[systems-shared]]

---

## 横切设计模式

所有管线共同遵循的架构约定：

→ [[design-patterns]]
