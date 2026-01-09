from ..models import (
    Actor,
    ActorCharacterSheet,
    ActorType,
    CharacterStats,
)
from .global_settings import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_SYSTEM_RULES,
)
from .utils import (
    create_actor,
)


def create_actor_orc() -> Actor:
    """
    创建一个兽人角色实例

    Returns:
        Actor: 兽人角色实例
    """
    return create_actor(
        name="角色.怪物.兽人-库洛斯",
        character_sheet=ActorCharacterSheet(
            name="orc",
            type=ActorType.ENEMY,
            profile="""你是兽人部族中的一员，出生于荒野之地。你从小就展现出强大的战斗力，长大后夺取了自己的小型战团，带领部下四处征战与掠夺。在追求力量与战利品的道路上，你逐渐形成了狂热的好战性格。但自从进入了新奥拉西斯，你开始接触到其他种族的文化与力量，逐渐意识到单靠蛮力无法在这个复杂的世界中生存下去，因此你学习了魔法和手工艺。""",
            appearance="""身材高大如巨人，肌肉紧绷，皮肤是深灰色的粗糙质感。额头上有一道丑陋的旧伤，横贯双眉，展现了他早年的激烈战斗痕迹。獠牙突出，双目中燃烧着好战的欲望。常穿着由兽皮和金属碎片拼接而成的胸甲，肩上披着大型凶兽的毛皮。背后则挂着一柄巨大的战斧，上面流动蓝色的纹路，似乎有魔法元素附着斧子。。""",
        ),
        # kick_off_message="",
        character_stats=CharacterStats(),
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        system_rules=FANTASY_WORLD_RPG_SYSTEM_RULES,
    )
