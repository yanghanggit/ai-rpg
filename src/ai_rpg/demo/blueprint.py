"""演示世界创建模块

提供工厂函数创建预配置的游戏世界，包括双角色和单角色版本。
"""

from typing import Final
from ..models import (
    Blueprint,
    WeaponItem,
    EquipmentItem,
)
from .actor_hunter import create_hunter
from .actor_mystic import create_mystic
from .global_settings import RPG_CAMPAIGN_SETTING
from .stage_ruins import (
    create_broken_wall_enclosure,
    create_stone_platform,
    # create_shi_family_house,
)
from .world_system_player_action_audit import create_player_action_audit
from .world_system_dungeon_generation import create_dungeon_generation


#######################################################################################################################
# 全局装备常量定义
#######################################################################################################################

# 武器装备
WEAPON_BONE_HUNTING_KNIFE: Final[WeaponItem] = WeaponItem(
    name="武器.兽骨猎刀",
    uuid="",
    description="以兽类前臂骨磨制的单刃猎刀，刃长一尺，锋利坚韧。刀柄缠以兽皮，握持稳固。刀身泛着暗黄色的骨质光泽。村中猎人常用的基础装备。",
    count=1,
)

WEAPON_BAMBOO_HUNTING_BOW: Final[WeaponItem] = WeaponItem(
    name="武器.竹弦狩猎弓",
    uuid="",
    description="以坚韧的山竹为弓臂，兽筋为弦，弓身刻有简单的兽纹。村中猎人常用的基础装备。",
    count=1,
)

# 防具装备
ARMOR_BEAST_LEATHER_SHIRT: Final[EquipmentItem] = EquipmentItem(
    name="防具.兽皮短衫",
    uuid="",
    description="以窃脂妖兽皮革缝制的轻便短衫，胸口和肩部用硬化兽皮加固，腰间系麻绳束带。适合山林间灵活移动。",
    count=1,
)


#######################################################################################################################
def create_hunter_mystic_blueprint(game_name: str) -> Blueprint:
    """
    创建演示游戏世界Blueprint实例 - 猎人与术士双角色版本。

    该函数创建一个包含猎人和术士两个角色的完整游戏世界，
    包含猎人备物所、村中议事堂和石氏木屋三个场景。两个角色为同伴关系,
    各自有不同的游戏目标。

    Args:
        game_name: 游戏世界的名称

    Returns:
        Blueprint: 初始化完成的游戏世界实例，包含:
            - 2个角色(猎人和术士)
            - 3个场景(猎人备物所、村中议事堂、石氏木屋)
            - 角色的初始kick_off_message
            - 预设的战役设定

    角色目标:
        - 猎人: 作为石氏猎人家族传人，磨练狩猎技艺，维护桃花源周边山林的生态平衡，
          并探索古先民遗迹的秘密
        - 术士: 通过研究古先民遗迹中的神秘符文，理解古先民引导自然之力的方法，
          并揭示桃花源隐藏的秘密
    """

    # 创建英雄营地场景和角色
    actor_hunter = create_hunter()

    # 添加猎人测试装备
    actor_hunter.items.extend(
        [
            WEAPON_BONE_HUNTING_KNIFE.model_copy(),
            ARMOR_BEAST_LEATHER_SHIRT.model_copy(),
        ]
    )

    # 直接使用外观描述，这样就减少一次推理生成。
    actor_hunter.character_sheet.appearance = "一名年近三十的男子，身形精悍，肌肉线条分明，是常年高强度活动留下的痕迹。他的肤色是经年风吹日晒形成的健康褐色。眼神沉静而警觉，下颌蓄着打理整齐的短须，头发在脑后简单束成一个发髻。他穿着一件轻便的短衫，由某种暗红色带细密纹路的皮革制成，胸口与肩部有颜色略深的加固部分，腰间用麻绳束紧。未被衣物覆盖的左肩处，清晰可见三道平行的、已经愈合的旧疤痕。他的右手虎口位置，皮肤因长期摩擦而显得格外粗糙厚实。"

    # 测试攻击力，打的快一点。
    actor_hunter.character_stats.attack = 100000

    # 创建术士角色
    actor_mystic = create_mystic()

    # 创建场景
    stage_broken_wall_enclosure = create_broken_wall_enclosure()
    stage_stone_platform = create_stone_platform()

    # 设置关系和消息，先都在这里设置好，后续如果需要调整也方便。
    stage_stone_platform.actors = [actor_hunter, actor_mystic]

    # 创建世界
    return Blueprint(
        name=game_name,
        player_actor=actor_hunter.name,  # 玩家角色为战士
        player_only_stage=stage_broken_wall_enclosure.name,
        campaign_setting=RPG_CAMPAIGN_SETTING,
        stages=[
            stage_broken_wall_enclosure,
            stage_stone_platform,
        ],
        world_systems=[create_player_action_audit(), create_dungeon_generation()],
    )


###############################################################################################################################
