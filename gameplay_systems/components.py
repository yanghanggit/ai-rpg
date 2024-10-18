from typing import NamedTuple, List


# 全局唯一标识符
class GUIDComponent(NamedTuple):
    name: str
    GUID: int


# 记录kick off信息
class KickOffComponent(NamedTuple):
    name: str
    content: str


# 例如，世界级的entity就标记这个组件
class WorldComponent(NamedTuple):
    name: str


# 场景标记
class StageComponent(NamedTuple):
    name: str


# 场景可以去往的地方
class StageGraphComponent(NamedTuple):
    name: str
    stage_graph: List[str]


# 角色标记
class ActorComponent(NamedTuple):
    name: str
    current_stage: str


# 玩家标记
class PlayerComponent(NamedTuple):
    name: str


# 摧毁Entity标记
class DestroyComponent(NamedTuple):
    name: str


# 自动规划的标记
class PlanningAllowedComponent(NamedTuple):
    name: str


# 角色外观信息
class AppearanceComponent(NamedTuple):
    name: str
    appearance: str
    hash_code: str


# 身体信息，用于和衣服组成完整的外观信息。如果是动物等，就是动物的外观信息
class BodyComponent(NamedTuple):
    name: str
    body: str


# 标记进入新的舞台
class EnterStageComponent(NamedTuple):
    name: str
    enter_stage: str


# RPG游戏的属性组件
class RPGAttributesComponent(NamedTuple):
    name: str
    maxhp: int
    hp: int
    attack: int
    defense: int


# RPG游戏的当前武器组件
class RPGCurrentWeaponComponent(NamedTuple):
    name: str
    propname: str


# RPG游戏的当前衣服组件
class RPGCurrentClothesComponent(NamedTuple):
    name: str
    propname: str
