# entitas

`ai-rpg` 使用的最小 ECS（Entity–Component–System）核心：把游戏的**数据**（组件）与**身份**（实体句柄）分离，由 `Context` 统一存储与查询，便于以线性流程编排游戏逻辑。

## 核心概念

| 概念 | 作用 |
| --- | --- |
| `Component` | 纯数据，Pydantic `BaseModel` 子类。 |
| `Context` | 组件存储 + 查询分组；实体的唯一归属。 |
| `Entity` | 轻量句柄，只持有 `(context, index, name)`，组件不在句柄上。 |
| `Matcher` | 组件条件：`all_of` / `any_of` / `none_of`。 |
| `Group` | 满足某 `Matcher` 的实体集合，随组件增删自动更新。 |
| `Collector` | 订阅 `Group` 的增删事件，收集待处理实体。 |
| `ReactiveProcessor` | 每帧「收集 → 过滤 → 批量处理」的处理器基类。 |
| `ProcessorPipeline` | 按 `Initialize → Execute → Cleanup → TearDown` 编排多个处理器。 |
| `Initialize/Execute/Cleanup/TearDownProcessor` | 处理器生命周期的抽象契约（`ABC`）。 |

## 最小用法

```python
from ai_rpg.entitas import Component, Context, Matcher


class Position(Component):
    x: float
    y: float


context = Context()

hero = context.create_entity()
hero.add(Position, 0.0, 0.0)             # 按字段顺序传参
# 或：hero.set(Position, Position(x=0.0, y=0.0))  # 直接放组件实例

for entity in context.get_group(Matcher(Position)).entities:
    print(entity, entity.get(Position))

hero.replace(Position, 9.0, 9.0)
hero.remove(Position)
context.destroy_entity(hero)
```

处理器（可选）：

```python
from ai_rpg.entitas import GroupEvent, Matcher, ProcessorPipeline, ReactiveProcessor


class OnMove(ReactiveProcessor):
    def get_trigger(self):
        return {Matcher(Position): GroupEvent.ADDED}

    def filter(self, entity) -> bool:
        return True

    async def react(self, entities) -> None:
        ...


pipeline = ProcessorPipeline()
pipeline.add(OnMove(context))
await pipeline.execute()
pipeline.cleanup()
```

## 序列化（dump / load）

以**实体名作 key** 的纯 dict 表示，只保存「重建 Context 核心」所需的组件；`pools` /
`handles` / `groups` / 事件接线 / 名称索引等运行期成员一律不存，加载时重建。

```python
ComponentData = dict[str, Any]              # 组件字段名 -> 值
EntityData    = dict[str, ComponentData]    # 组件类型名 -> 组件数据
ContextData   = dict[str, EntityData]       # 实体名 -> 实体数据

dump_entity(entity, *, component_filter=None) -> EntityData
dump_components(*components) -> EntityData                      # 由组件实例直接构造
dump_entities(entities, *, component_filter=None) -> ContextData
dump_context(context, *, component_filter=None) -> ContextData  # 按 slot index 顺序
load_context(context, data, resolve_type) -> dict[str, Entity]  # 注入 resolver，静默写入
```

```python
from ai_rpg.entitas import Context, dump_components, dump_context, load_context


# 导出：{"hero": {"Position": {"x": 1.0, "y": 2.0}}}
data = dump_context(context)

# 蓝图/工厂里直接构造：{"Position": {"x": 1.0, "y": 2.0}, "Marker": {}}
entity_data = dump_components(Position(x=1.0, y=2.0), Marker())


# 还原进一个空 Context（组件类型名 -> 类 由调用方注入）
def resolve(name: str, comp_data: dict) -> type:
    return {"Position": Position, "Marker": Marker}[name]


restored = load_context(Context(), data, resolve)
```

契约：

- `dump_*` 要求实体 `name` **非空且唯一**（重名会静默丢数据）。
- `load_context` 仅用于**空 Context**；直接写 storage、**不触发组件事件**，故分组应在 load 之后创建。
- entitas 不认识组件注册表：类型解析由 `resolve_type` 注入（游戏层用 `resolve_component_type`）。

## 设计要点

- **index 化存储**：组件按类型分池 `dict[type, list]`，用实体 `index` 直寻址（sparse-set / SoA）。
- **实体即句柄**：身份 = 句柄对象本身；`index` 只用于在 `Context` 中定位组件，槽位不做回收/复用。
- **查询**：`Group` 内部只存 `index`，`entities` 按需物化句柄；组件变更通过事件增量维护。
- **类型解耦**：`ContextProtocol`（`typing.Protocol`）以结构化类型描述 `Context` 对外接口，避免 `Entity`/`Group` 与 `Context` 的循环导入。
- **导入统一**：使用者只需 `from ai_rpg.entitas import ...`。

## 说明

- 所有组件必须继承 `entitas.components.Component`（基于 Pydantic `BaseModel`）。
- 测试用的通用组件放在 `tests/ecs_testing.py`，**不属于发布包**。
