from typing import Any, Dict, Final, NamedTuple, List, final
from .dungeon import Skill, StatusEffect
from .objects import RPGCharacterProfile
from .registry import register_component_class


############################################################################################################
# 全局唯一标识符 RunTimeIndexComponent
@final
@register_component_class
class RuntimeComponent(NamedTuple):
    name: str
    runtime_index: int


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
class EnvironmentComponent(NamedTuple):
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
    action_order: List[str]


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
@final
@register_component_class
class CanStartPlanningComponent(NamedTuple):
    name: str


############################################################################################################
# 标记player主动行动。
@final
@register_component_class
class PlayerActiveComponent(NamedTuple):
    name: str


############################################################################################################
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

    @staticmethod
    def __deserialize_component__(component_data: Dict[str, Any]) -> None:
        key: Final[str] = "skills"
        assert key in component_data
        if key in component_data:
            component_data[key] = [Skill(**skill) for skill in component_data[key]]


############################################################################################################
# 死亡标记
@final
@register_component_class
class DeathComponent(NamedTuple):
    name: str


############################################################################################################
############################################################################################################
############################################################################################################
# 新版本的重构！
@final
@register_component_class
class RPGCharacterProfileComponent(NamedTuple):
    name: str
    rpg_character_profile: RPGCharacterProfile
    status_effects: List[StatusEffect]

    @staticmethod
    def __deserialize_component__(component_data: Dict[str, Any]) -> None:
        assert "rpg_character_profile" in component_data
        if "rpg_character_profile" in component_data:
            component_data["rpg_character_profile"] = RPGCharacterProfile(
                **component_data["rpg_character_profile"]
            )

        assert "status_effects" in component_data
        if "status_effects" in component_data:
            component_data["status_effects"] = [
                StatusEffect(**effect) for effect in component_data["status_effects"]
            ]

    @property
    def attrs_prompt(self) -> str:
        return f"""- 当前生命：{self.rpg_character_profile.hp}
- 最大生命：{self.rpg_character_profile.max_hp}
- 物理攻击：{self.rpg_character_profile.physical_attack}
- 物理防御：{self.rpg_character_profile.physical_defense}
- 魔法攻击：{self.rpg_character_profile.magic_attack}
- 魔法防御：{self.rpg_character_profile.magic_defense}"""

    @property
    def status_effects_prompt(self) -> str:
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
############################################################################################################
############################################################################################################


# 问号牌
@final
@register_component_class
class XCardPlayerComponent(NamedTuple):
    name: str
    skill: Skill

    @staticmethod
    def __deserialize_component__(component_data: Dict[str, Any]) -> None:
        assert "skill" in component_data
        if "skill" in component_data:
            component_data["skill"] = Skill(**component_data["skill"])
