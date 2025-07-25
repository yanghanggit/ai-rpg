from typing import Any, Dict, NamedTuple, List, final
from pydantic import BaseModel
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
    uuid: str


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


@final
# @register_base_model_class
class HandDetail(BaseModel):
    skill: str
    targets: List[str]
    reason: str
    dialogue: str


# 手牌组件。
@final
@register_component_class
class HandComponent(NamedTuple):
    name: str
    skills: List[Skill]
    details: List[HandDetail]

    @staticmethod
    def deserialize_component_data(component_data: Dict[str, Any]) -> Dict[str, Any]:

        processed_data = component_data.copy()
        assert "skills" in processed_data, "HandComponent must have skills."
        if "skills" in processed_data:
            processed_data["skills"] = [
                Skill(**skill) for skill in processed_data["skills"]
            ]

        assert "details" in processed_data, "HandComponent must have details."
        if "details" in processed_data:
            processed_data["details"] = [
                HandDetail(**detail) for detail in processed_data["details"]
            ]

        return processed_data

    def get_skill(self, skill_name: str) -> Skill:
        for skill in self.skills:
            if skill.name == skill_name:
                return skill
        return Skill(name="", description="", effect="")

    def get_detail(self, skill_name: str) -> HandDetail:
        for detail in self.details:
            if detail.skill == skill_name:
                return detail
        return HandDetail(skill="", targets=[], reason="", dialogue="")


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
    def deserialize_component_data(component_data: Dict[str, Any]) -> Dict[str, Any]:
        processed_data = component_data.copy()

        assert (
            "rpg_character_profile" in processed_data
        ), "RPGCharacterProfileComponent must have a rpg_character_profile."
        if "rpg_character_profile" in processed_data:
            processed_data["rpg_character_profile"] = RPGCharacterProfile(
                **processed_data["rpg_character_profile"]
            )

        assert (
            "status_effects" in processed_data
        ), "RPGCharacterProfileComponent must have status_effects."
        if "status_effects" in processed_data:
            processed_data["status_effects"] = [
                StatusEffect(**effect) for effect in processed_data["status_effects"]
            ]

        return processed_data

    @property
    def attrs_prompt(self) -> str:
        return f"""- 生命:{self.rpg_character_profile.hp}/{self.rpg_character_profile.max_hp}
- 物理攻击:{self.rpg_character_profile.physical_attack}
- 物理防御:{self.rpg_character_profile.physical_defense}
- 魔法攻击:{self.rpg_character_profile.magic_attack}
- 魔法防御:{self.rpg_character_profile.magic_defense}"""

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
    def deserialize_component_data(component_data: Dict[str, Any]) -> Dict[str, Any]:
        processed_data = component_data.copy()
        assert "skill" in processed_data, "XCardPlayerComponent must have a skill."
        if "skill" in processed_data:
            processed_data["skill"] = Skill(**processed_data["skill"])
        return processed_data


############################################################################################################
############################################################################################################
############################################################################################################
