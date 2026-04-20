"""演示世界创建模块

提供工厂函数创建预配置的游戏世界，包括双角色和单角色版本。
"""

from ..models import (
    Blueprint,
    CharacterStats,
    EquipmentItem,
    EquipmentType,
    UniqueItem,
    WeaponItem,
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

    # 调整旅行者的速度属性，增加其在 SPEED_ORDER 策略下的出手优先级
    actor_wanderer.character_stats.speed = 20

    # 为旅行者分配初始装备：猎刀 + 轻甲套装 + 沙漠护身符
    actor_wanderer.items = [
        WeaponItem(
            name="缺口猎刀",
            uuid="",
            description="一把刀身偏短的猎刀，刃背厚实，靠近刀尖三分之一处有一道浅缺口，像是曾经硬撬过什么。握柄以粗布条缠绕，布已泛黄，但缠法整齐，显然出自熟练的手。旅行者醒来时它插在腰带侧边，不知何时放上去的，但握在手里有一种说不清的熟悉感。",
            stat_bonuses=CharacterStats(
                hp=0, max_hp=0, attack=2, defense=0, action_count=0, speed=0
            ),
        ),
        EquipmentItem(
            name="沙漠旅行者轻甲",
            uuid="",
            description="一套轻便的皮质护甲，由多块经过硬化处理的皮革拼接而成，覆盖躯干、肩部与小腿。设计简洁，不妨碍快速移动，表面留有风沙打磨的痕迹，像是在沙漠中经历过漫长跋涉。",
            equipment_type=EquipmentType.ARMOR,
            stat_bonuses=CharacterStats(
                hp=0, max_hp=0, attack=0, defense=2, action_count=0, speed=0
            ),
        ),
        EquipmentItem(
            name="裂纹护身符",
            uuid="",
            description="一枚形状不规则的石质护符，中央有一道细小的裂缝，边缘被磨得光滑。来历不明，但旅行者醒来时它就挂在颈间，像是某种提醒，或某种残留。",
            equipment_type=EquipmentType.ACCESSORY,
            stat_bonuses=CharacterStats(
                hp=0, max_hp=0, attack=1, defense=1, action_count=0, speed=0
            ),
        ),
    ]

    # 创建学者角色
    actor_mystic = create_scholar()

    # 为学者分配初始装备：残破笔记本 + 学者长袍套装 + 记忆碎片项链
    actor_mystic.items = [
        UniqueItem(
            name="残破笔记本",
            uuid="",
            description="一本封皮已经破损的小开本笔记，内页密密麻麻写满了文字——字迹是维拉自己的，她一眼就认出来了。内容涉及某些地点的方位、符文图样的草稿、以及偶尔出现的只言片语，像是给自己留的备忘，但她对其中任何一条都毫无印象。最后几页空白，最末一行写着：'如果你看到这里，说明计划出了问题。'",
        ),
        EquipmentItem(
            name="学者灰袍",
            uuid="",
            description="一件质地粗糙的浅灰色长袍，款式简朴而宽松，带有宽袖与深兜帽。袖口与下摆因拖曳留有沙土的痕迹，腰间以窄皮带束紧。整体设计偏向学术而非战斗，但厚实的布料能提供基本的防护。",
            equipment_type=EquipmentType.ARMOR,
            stat_bonuses=CharacterStats(
                hp=0, max_hp=0, attack=0, defense=2, action_count=0, speed=0
            ),
        ),
        EquipmentItem(
            name="记忆碎片项链",
            uuid="",
            description="一条由细银链串起的项链，坠子是一块半透明的矿石碎片，内部隐约有细纹如文字蜿蜒。维拉在翻阅残破笔记时发现它夹在最后一页——上面用相同的笔迹写着：'不要摘下它。'",
            equipment_type=EquipmentType.ACCESSORY,
            stat_bonuses=CharacterStats(
                hp=0, max_hp=0, attack=1, defense=1, action_count=0, speed=0
            ),
        ),
    ]

    # 创建场景
    stage_broken_wall_enclosure = create_broken_wall_enclosure()
    stage_stone_platform = create_stone_platform()

    # 设置关系和消息，先都在这里设置好，后续如果需要调整也方便。
    stage_stone_platform.actors = [actor_wanderer, actor_mystic]

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
        world_systems=[create_player_action_audit(), create_dungeon_generation()],
    )


###############################################################################################################################
