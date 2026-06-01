"""演示世界创建模块

提供工厂函数创建预配置的游戏世界，包括双角色和单角色版本。
"""

from ..models import (
    Blueprint,
    CostumeItem,
    GearItem,
    ConsumableItem,
    MaterialItem,
    TargetType,
    CharacterStats,
)
from .actor_wanderer import create_wanderer
from .actor_scholar import create_scholar
from .global_settings import RPG_CAMPAIGN_SETTING
from .stage_ruins import (
    create_broken_wall_enclosure,
    create_stone_platform,
)
from .world_system_player_action_audit import create_player_action_audit
from .world_system_dungeon_generation import create_dungeon_generation
from .world_system_workshop import create_workshop


#######################################################################################################################
def create_ruins_blueprint(game_name: str) -> Blueprint:
    """
    创建演示游戏世界Blueprint实例 - 旅行者与学者双角色版本。

    包含断壁石室和石台广场两个场景，两名失忆者在沙漠残垣遗迹中醒来。

    Args:
        game_name: 游戏世界的名称

    Returns:
        Blueprint: 初始化完成的游戏世界实例
    """

    # 创建英雄营地场景和角色
    actor_wanderer = create_wanderer()
    actor_wanderer.custom_item = CostumeItem(
        name="时装.旅行者风尘斗篸",
        description="一件覆盖全身的宽幅斗篷，布料经风沙磨砺后呈不均匀的赭石色，边缘绣有简单的几何暗纹。披上后显得愈发像一名经历颇丰的旅人。",
    )

    # 调整旅行者的速度属性，增加其在 SPEED_ORDER 策略下的出手优先级
    actor_wanderer.character_stats.speed = 2

    # 创建学者角色
    actor_scholar = create_scholar()
    actor_scholar.custom_item = CostumeItem(
        name="时装.学者墨纹长袍",
        description="一件深灰色长袍，袖口与衣摆绣有已褪色的墨色卷轴图案。穿上后气质沉稳，颇有远行学者的风范。",
    )

    # 创建场景
    stage_broken_wall_enclosure = create_broken_wall_enclosure()
    stage_stone_platform = create_stone_platform()

    # 设置关系和消息，先都在这里设置好，后续如果需要调整也方便。
    stage_stone_platform.actors = [actor_wanderer, actor_scholar]

    # 创建世界
    return Blueprint(
        name=game_name,
        player_actor=actor_wanderer.name,  # 玩家角色为战士
        player_only_stage=stage_broken_wall_enclosure.name,
        campaign_setting=RPG_CAMPAIGN_SETTING,
        stages=[
            stage_broken_wall_enclosure,
            stage_stone_platform,
        ],
        world_systems=[
            create_player_action_audit(),
            create_dungeon_generation(),
            create_workshop(),
        ],
        storage_entity="世界储物箱",
        items=[
            GearItem(
                name="装备.缺口猎刀",
                description="一把刀身偏短的猎刀，刃背厚实，靠近刀尖三分之一处有一道浅缺口，像是曾经硬撬过什么。握柄以粗布条缠绕，布已泛黄，但缠法整齐，显然出自熟练的手。",
                stat_bonuses=CharacterStats(
                    hp=0, max_hp=0, attack=2, defense=0, energy=0, speed=0
                ),
            ),
            GearItem(
                name="装备.沙漠旅行者轻甲",
                description="一套轻便的皮质护甲，由多块经过硬化处理的皮革拼接而成，覆盖躯干、肩部与小腿。设计简洁，不妨碍快速移动，表面留有风沙打磨的痕迹。",
                stat_bonuses=CharacterStats(
                    hp=0, max_hp=0, attack=0, defense=2, energy=0, speed=0
                ),
            ),
            ConsumableItem(
                name="消耗品.裂口草药包",
                description="几片晒干的草叶压在一小块粗布里，散发着轻微的苦涩气味。不知用途，但直觉告诉你可以往伤口上敷。使用后应能小量恢复生命值。",
                count=2,
                target_type=TargetType.SELF_ONLY,
            ),
            ConsumableItem(
                name="消耗品.沙蝎毒液瓶",
                description="一个封口严密的小玻璃瓶，瓶内液体呈深黄色，偶尔能看到细小气泡浮起。标签已模糊，隐约能辨认出一个骷髅图案。向单个敌人投掷可造成毒性伤害。",
                count=2,
                target_type=TargetType.ENEMY_SINGLE,
            ),
            MaterialItem(
                name="材料.沙漠草叶",
                description="在沙漠边缘采集的干燥草叶，叶脉间残留淡淡苦涩气味。据说直接敷于伤口有止血消炎之效。",
                count=3,
            ),
            MaterialItem(
                name="材料.毒蝶触须",
                description="一小段细长的蝶须，表面残留黄色液迹，低温时凝固为粉末状。密封保存，含微量化学毒素。",
                count=2,
            ),
            MaterialItem(
                name="材料.废旧皮革",
                description="一块拳头大小的硬化皮革碎片，边缘粗糙，切割痕迹清晰可辨。可用于绑扎或简单防护。",
                count=2,
            ),
        ],
    )


###############################################################################################################################
