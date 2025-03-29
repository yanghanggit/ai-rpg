from typing import Final, NamedTuple, List, final
from components.registry import register_component_class
from models.v_0_0_1 import Skill, StatusEffect


# 注意，不允许动！
SCHEMA_VERSION: Final[str] = "0.0.1"


# 全局唯一标识符
@final
@register_component_class
class GUIDComponent(NamedTuple):
    name: str
    GUID: int


############################################################################################################
# 记录kick off原始信息
@final
@register_component_class
class KickOffMessageComponent(NamedTuple):
    name: str
    content: str


############################################################################################################
# 标记kick off已经完成
@final
@register_component_class
class KickOffDoneComponent(NamedTuple):
    name: str


############################################################################################################
# 例如，世界级的entity就标记这个组件
@final
@register_component_class
class WorldSystemComponent(NamedTuple):
    name: str


############################################################################################################
# 场景标记
@final
@register_component_class
class StageComponent(NamedTuple):
    name: str


############################################################################################################
# 记录场景的描述 #Environment
@final
@register_component_class
class StageEnvironmentComponent(NamedTuple):
    name: str
    narrate: str


############################################################################################################
# 角色标记
@final
@register_component_class
class ActorComponent(NamedTuple):
    name: str
    current_stage: str


############################################################################################################
# 玩家标记
@final
@register_component_class
class PlayerComponent(NamedTuple):
    player_name: str


############################################################################################################
# 摧毁Entity标记
@final
@register_component_class
class DestroyComponent(NamedTuple):
    name: str


############################################################################################################
# 角色外观信息
@final
@register_component_class
class AppearanceComponent(NamedTuple):
    name: str
    appearance: str


############################################################################################################
# Stage专用，标记该Stage是Home
@final
@register_component_class
class HomeComponent(NamedTuple):
    name: str


############################################################################################################
# Stage专用，标记该Stage是Dungeon
@final
@register_component_class
class DungeonComponent(NamedTuple):
    name: str


############################################################################################################
# Actor专用，标记该Actor是Hero
@final
@register_component_class
class HeroComponent(NamedTuple):
    name: str


############################################################################################################
# Actor专用，标记该Actor是Monster
@final
@register_component_class
class MonsterComponent(NamedTuple):
    name: str


############################################################################################################
# Actor专用，标记该Actor需要进行角色扮演推理（心理活动，说话...），如有需要，单独列入Plan
@final
@register_component_class
class ActorPermitComponent(NamedTuple):
    name: str


############################################################################################################
# State专用，标记该State需要进行场景描写推理，如有需要，单独列入Plan
@final
@register_component_class
class StagePermitComponent(NamedTuple):
    name: str


# 以下是针对卡牌游戏中 牌组、弃牌堆、抽牌堆、手牌 的类名设计建议，结合常见游戏术语和编程习惯：
# 方案 4：极简统一型
# 组件	类名	说明
# 牌组	Deck	直接命名为 Deck，表示通用牌组。
# 抽牌堆	DrawDeck	与 Deck 统一，通过前缀区分功能。
# 弃牌堆	DiscardDeck	同上，保持命名一致性。
# 手牌	Hand	简洁无冗余。
# play_card
# draw_card
############################################################################################################
# 手牌组件。
@final
@register_component_class
class HandComponent(NamedTuple):
    name: str
    skills: List[Skill]


############################################################################################################
# 战斗中临时使用。
@final
@register_component_class
class CombatAttributesComponent(NamedTuple):
    name: str
    hp: float
    max_hp: float
    physical_attack: float
    physical_defense: float
    magic_attack: float
    magic_defense: float

    @property
    def as_prompt(self) -> str:
        return f"""- 当前生命：{self.hp}
- 最大生命：{self.max_hp}
- 物理攻击：{self.physical_attack}
- 物理防御：{self.physical_defense}
- 魔法攻击：{self.magic_attack}
- 魔法防御：{self.magic_defense}"""


############################################################################################################
# 战斗中临时使用。
@final
@register_component_class
class CombatStatusEffectsComponent(NamedTuple):
    name: str
    status_effects: List[StatusEffect]

    @property
    def as_prompt(self) -> str:
        ret = "- 无"
        if len(self.status_effects) > 0:
            ret = "\n".join(
                [
                    f"- {effect.name}: {effect.description} (剩余{effect.rounds}回合)"
                    for effect in self.status_effects
                ]
            )
        return ret


############################################################################################################
# 死亡标记
@final
@register_component_class
class DeathComponent(NamedTuple):
    name: str
