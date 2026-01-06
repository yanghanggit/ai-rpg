from .actor_training_robot import create_actor_training_robot
from ..models import Dungeon, Stage, StageType, Item, ItemType
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    FANTASY_WORLD_RPG_GAME_COMBAT_MECHANICS,
)
from .utils import (
    create_stage,
)


def create_stage_cave5() -> Stage:
    """
    创建一个训练场场景实例

    Returns:
        Stage: 训练场场景实例
    """
    return create_stage(
        name="场景.训练场",
        character_sheet_name="training_ground",
        kick_off_message=""" """,
        type=StageType.DUNGEON,
        stage_profile="""你是位于新奥拉西斯「尘烟裂谷」区深处的冒险者庄园里的一处改造训练场，原本是废弃的遗迹通风井，被冒险者公会改造为实战模拟场所，用于测试战斗策略与磨炼技艺。
地形被刻意改造成沼泽环境以模拟恶劣战斗条件，场地中散布着干草人偶和木质击打桩作为训练目标，地面积水与沼气混合形成潮湿浑浊的空气，生锈的武器残片和漂白的生物骸骨被插在泥泞中作为环境标记，营造出危险区域的真实氛围。
注意！你是一个动态响应的场景，角色的物理行为与魔法交互会对环境产生实际影响并改变场景状态，这些变化会反过来影响后续行动的条件。""",
        actors=[],
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
        global_combat_mechanics=FANTASY_WORLD_RPG_GAME_COMBAT_MECHANICS,
    )


def create_demo_dungeon5() -> Dungeon:

    actor_training_robot = create_actor_training_robot()
    actor_training_robot.character_stats.hp = 1
    actor_training_robot.kick_off_message = (
        f"""# 游戏启动！告诉我你是谁？请说出你的全名。回答简短(<100字)。"""
    )
    actor_training_robot.items.append(
        Item(
            name="传奇道具.永恒符文核心",
            uuid="",
            type=ItemType.UNIQUE_ITEM,
            description="""你内部嵌入的魔法符文核心，赋予你不灭的生命力。
每当你的生命值降到0时，符文核心会自动将你的生命恢复到Max_HP。
如果你还没有'永恒符文核心'相关的status_effect，则在第一次更新状态时创建一个，标记此道具的存在，duration=99999。
后续回合系统会自动维护此状态效果，无需重复创建。
当你的生命值降到0时，符文核心会让你周身冒出微弱的符文光芒并坚挺地站立着，自身恢复到完美状态。""",
        )
    )

    stage_cave5 = create_stage_cave5()
    stage_cave5.actors = [actor_training_robot]
    stage_cave5.kick_off_message = f"""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。"""

    return Dungeon(
        name="训练场",
        stages=[
            stage_cave5,
        ],
    )
