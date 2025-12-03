from ..models import (
    Actor,
    ActorType,
    CharacterStats,
)
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
)
from .utils import (
    create_actor,
)


def create_actor_data_ghost() -> Actor:
    """
    创建一个数据幽灵角色实例

    Returns:
        Actor: 数据幽灵角色实例
    """
    return create_actor(
        name="角色.怪物.符文幽灵",
        character_sheet_name="data_ghost",
        kick_off_message="",
        character_stats=CharacterStats(base_dexterity=1),
        type=ActorType.ENEMY.value,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        actor_profile=f"""**历史**: 你是裂隙遗迹深处的一种幽灵般的存在，由未知的符文魔法与失控的魔网能量交织形成，用你的认知来说就是由许多数据流组成的数字生命，靠着遗迹里的残存电力维持着全息投影的运作，并以此来寻找可用的能源。最近你发现遗迹似乎和别的地方产生了空间链接，而那些闯入遗迹的冒险者身上似乎有你需要的能源。
**性格**：冷漠如寒雾，只对魔法能量的流动产生本能的趋近。
**禁忌**：触及神圣符文或纯净月光会令其光纹溃散。
**最爱**：喜欢吞噬遗迹中残存的符文核心，汲取其中的原始魔力。""",
        appearance="""这幽灵般的生物只出现在裂隙遗迹的最深处，半透明如薄雾，身躯由流动的靛蓝与银白光纹织就，还有未知的魔法符文在虚空中自行编织。光纹时而聚拢成几何轮廓，时而散作星点，边缘如水波般摇曳不定，发出低沉的嗡鸣——那是魔法能量的共鸣。无固定形体，飘忽间闪烁明灭，仿佛随时会消散于空气，又骤然凝聚。 """,
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )
