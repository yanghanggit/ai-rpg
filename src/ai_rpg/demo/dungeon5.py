from .actor_training_robot import create_actor_training_robot
from ..models import Dungeon, Stage, StageProfile, StageType, UniqueItem
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
    RPG_SYSTEM_RULES,
    RPG_COMBAT_MECHANICS,
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
        stage_profile=StageProfile(
            name="training_ground",
            type=StageType.DUNGEON,
            profile="""你是位于新奥拉西斯「尘烟裂谷」区深处的冒险者庄园里的一处改造训练场，原本是废弃的遗迹通风井，被冒险者公会改造为实战模拟场所，用于测试战斗策略与磨炼技艺。
地形被刻意改造成沼泽环境以模拟恶劣战斗条件，场地中散布着干草人偶和木质击打桩作为训练目标，地面积水与沼气混合形成潮湿浑浊的空气，生锈的武器残片和漂白的生物骸骨被插在泥泞中作为环境标记，营造出危险区域的真实氛围。
注意！你是一个动态响应的场景，角色的物理行为与魔法交互会对环境产生实际影响并改变场景状态，这些变化会反过来影响后续行动的条件。""",
        ),
        # kick_off_message=""" """,
        # actors=[],
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        combat_mechanics=RPG_COMBAT_MECHANICS,
    )


def create_demo_dungeon5() -> Dungeon:

    actor_training_robot = create_actor_training_robot()
    actor_training_robot.character_stats.hp = 1
    actor_training_robot.kick_off_message = (
        f"""# 游戏启动！告诉我你是谁？请说出你的全名。回答简短(<100字)。"""
    )
    actor_training_robot.items.append(
        UniqueItem(
            name="传奇道具.永恒符文核心",
            uuid="",
            description="""你内部嵌入的魔法符文核心，赋予你不灭的生命力。第一回合必须生成一个名为"永恒符文核心"的状态效果(duration=99999)，状态效果的描述为：内部符文核心持续运转，赋予不灭的生命力，当生命值降到0时自动恢复到满血状态。""",
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
