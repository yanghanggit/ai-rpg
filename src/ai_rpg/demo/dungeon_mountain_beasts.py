from ..models import (
    Dungeon,
    StageProfile,
    StageType,
)
from .actor_mountain_monkey import create_actor_mountain_monkey
from .actor_mountain_tiger import create_actor_mountain_tiger
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
    RPG_SYSTEM_RULES,
    RPG_COMBAT_MECHANICS,
)
from .entity_factory import (
    create_stage,
)


def create_mountain_beasts_dungeon() -> Dungeon:
    """
    创建山林妖兽狩猎副本。

    包含两个递进式场景：
    - 山林边缘：精怪级山魈，擅长利用环境物品作战
    - 密林深处：大妖级山中虎，生态链顶点的强大妖兽

    Returns:
        Dungeon: 山林妖兽副本实例
    """
    # 创建山魈栖息地场景（山林边缘）
    stage_forest_edge = create_stage(
        name="场景.山林边缘",
        stage_profile=StageProfile(
            name="forest_edge",
            type=StageType.DUNGEON,
            profile="山脉的山林边缘地带，树木稀疏，地面散落着石块、断枝和干燥的落叶。周围有多处适合攀爬的岩石和树干，视野相对开阔。",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        combat_mechanics=RPG_COMBAT_MECHANICS,
    )

    # 添加山魈作为场景中的敌对角色
    actor_monkey = create_actor_mountain_monkey()

    # 将山魈的生命值设为1，方便测试击杀
    actor_monkey.character_stats.hp = 1

    # 将山魈添加到场景的角色列表中
    stage_forest_edge.actors = [actor_monkey]

    # 设置场景启动消息，指导游戏如何描写环境
    stage_forest_edge.kick_off_message = f"""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。"""

    # 创建山中虎领地场景（密林深处）
    stage_deep_forest = create_stage(
        name="场景.密林深处",
        stage_profile=StageProfile(
            name="deep_forest",
            type=StageType.DUNGEON,
            profile="山脉的密林深处，古木参天遮蔽天日，地面铺满厚重的腐叶。粗壮的树干上留有深深的爪痕，周围散布着巨大的兽骨。空气沉闷压抑，弥漫着强烈的兽类气息。",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        combat_mechanics=RPG_COMBAT_MECHANICS,
    )

    # 添加山中虎作为场景中的敌对角色
    actor_tiger = create_actor_mountain_tiger()

    # 将山中虎的生命值设为1，方便测试击杀
    actor_tiger.character_stats.hp = 1

    # 将山中虎添加到场景的角色列表中
    stage_deep_forest.actors = [actor_tiger]

    # 设置场景启动消息，指导游戏如何描写环境
    stage_deep_forest.kick_off_message = f"""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
    
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。"""

    return Dungeon(
        name="地下城.山林妖兽",
        stages=[
            stage_forest_edge,
            stage_deep_forest,
        ],
    )


def create_tiger_lair_dungeon() -> Dungeon:
    """
    创建山中虎巢穴副本。

    包含单个场景：
    - 密林深处：大妖级山中虎，生态链顶点的强大妖兽

    Returns:
        Dungeon: 山中虎巢穴副本实例
    """
    # 创建山中虎领地场景（密林深处）
    stage_deep_forest = create_stage(
        name="场景.密林深处",
        stage_profile=StageProfile(
            name="deep_forest",
            type=StageType.DUNGEON,
            profile="山脉的密林深处，古木参天遮蔽天日，地面铺满厚重的腐叶。粗壮的树干上留有深深的爪痕，周围散布着巨大的兽骨。空气沉闷压抑，弥漫着强烈的兽类气息。",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        combat_mechanics=RPG_COMBAT_MECHANICS,
    )

    # 添加山中虎作为场景中的敌对角色
    actor_tiger = create_actor_mountain_tiger()

    # 将山中虎的生命值设为1，方便测试击杀
    # actor_tiger.character_stats.hp = 2

    # 准备测试穿透防御的攻击力，所以防御力设高一些
    actor_tiger.character_stats.defense = 100

    # 将山中虎添加到场景的角色列表中
    stage_deep_forest.actors = [actor_tiger]

    # 设置场景启动消息，指导游戏如何描写环境
    stage_deep_forest.kick_off_message = f"""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
    
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。"""

    return Dungeon(
        name="地下城.山中虎巢穴",
        stages=[
            stage_deep_forest,
        ],
    )
