from ..models import (
    Actor,
    ActorType,
    RPGCharacterProfile,
)
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .utils import (
    create_actor,
)


def create_actor_slime() -> Actor:
    """
    创建一个史莱姆角色实例

    Returns:
        Actor: 史莱姆角色实例
    """
    return create_actor(
        name="角色.怪物.史莱姆-史黏黏",
        character_sheet_name="slime",
        kick_off_message="",
        rpg_character_profile=RPGCharacterProfile(base_dexterity=1),
        type=ActorType.MONSTER,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        actor_profile="""你是史莱姆，生活在阴暗潮湿的洞穴中。虽然外表柔软，但你拥有强大的分裂能力、再生能力和独特的变形能力。""",
        appearance="""身型似椭圆形的球体，呈现出半透明的果冻状，颜色从浅绿色渐变为深绿色。表面光滑，偶尔闪烁着微弱的光芒。头部没有明显的面孔，只有两个发光的蓝色点作为眼睛。你可以喷射腐蚀性液体来攻击敌人，也可以附着在生物头部来让人窒息。""",
    )
