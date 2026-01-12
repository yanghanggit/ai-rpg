from .actor_training_dummy import create_training_dummy
from .stage_village import create_training_ground
from ..models import Dungeon, UniqueItem, StageType


def create_training_dungeon() -> Dungeon:
    """
    创建猎人训练场地下城实例。

    该函数创建一个包含训练木桩的简单地下城，用于猎人学徒和猎人们
    日常磨练武器技巧和战斗技能。训练木桩内嵌有建木心节，能够在被击毁后
    自动修复，适合反复训练使用。

    地下城组成:
        - 1个训练场景（猎人训练场）
        - 1个训练木桩（生命值1，配备青木妖心节自动修复）

    训练木桩特性:
        - 使用建木大妖的心节素材，具备自我修复能力
        - 被击败后会自动恢复至完好状态
        - 适合初学者反复练习基础战斗技巧

    Returns:
        Dungeon: 初始化完成的训练场地下城实例，包含:
            - 名称: "地下城.猎人训练场"
            - 1个训练场景
            - 1个可自动修复的训练木桩

    Note:
        这是一个基础训练用地下城，不包含真实的妖兽威胁，
        适合新手猎人熟悉战斗系统和武器操作。
    """

    # 创建训练木桩角色
    actor_training_dummy = create_training_dummy()
    actor_training_dummy.character_stats.hp = 1
    actor_training_dummy.kick_off_message = (
        f"""# 游戏启动！告诉我你是谁？请说出你的全名。回答简短(<100字)。"""
    )
    actor_training_dummy.items.append(
        UniqueItem(
            name="特殊道具.青木妖心节",
            uuid="",
            description="""你的楠木主干内嵌有一截来自竹木大妖"建木"的心节。建木乃上古异种巨木，其心节即使离体也保持着旺盛的生命力，能持续生长修复周围的木质结构。第一回合必须生成一个名为"青木妖心节"的状态效果(duration=99999)，状态效果的描述为：体内建木心节的生命力维持着木桩结构的完整，当躯体被击毁（生命值降到0）时，心节会催生新的木质纤维，自动修复木桩至完好状态。""",
        )
    )

    # 创建训练场景
    stage_training_ground = create_training_ground()
    assert (
        stage_training_ground.stage_profile.type == StageType.DUNGEON
    ), "猎人训练场的StageType应为DUNGEON"
    stage_training_ground.actors = [actor_training_dummy]

    stage_training_ground.kick_off_message = f"""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。"""

    return Dungeon(
        name="地下城.训猎人训练场",
        stages=[
            stage_training_ground,
        ],
    )
