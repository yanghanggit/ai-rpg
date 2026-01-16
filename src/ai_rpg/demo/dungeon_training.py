from .actor_training_dummy import create_training_dummy
from .stage_village import create_training_ground
from ..models import Dungeon, UniqueItem, StageType


def create_training_dungeon() -> Dungeon:
    """创建猎人训练场地下城实例

    Returns:
        包含训练场景和可自动修复训练木桩的地下城
    """

    # 创建训练木桩角色
    actor_training_dummy = create_training_dummy()

    # 故意测试将生命值设为1，方便训练时快速击败
    actor_training_dummy.character_stats.hp = 1

    # 设置游戏启动对话
    actor_training_dummy.kick_off_message = (
        f"""# 游戏启动！告诉我你是谁？请说出你的全名。回答简短(<100字)。"""
    )

    # 因为故意将生命值设为1，所以需要添加自动修复道具
    actor_training_dummy.items.append(
        UniqueItem(
            name="特殊道具.青木妖心节",
            uuid="",
            description="""你的楠木主干内嵌有一截来自竹木大妖"建木"的心节。建木乃上古异种巨木，其心节即使离体也保持着旺盛的生命力，能持续生长修复周围的木质结构。""",
        )
    )

    # 创建训练场景
    stage_training_ground = create_training_ground()
    assert (
        stage_training_ground.stage_profile.type == StageType.DUNGEON
    ), "猎人训练场的StageType应为DUNGEON"

    # 将训练木桩添加到训练场景中
    stage_training_ground.actors = [actor_training_dummy]

    # 设置训练场景的游戏启动对话
    stage_training_ground.kick_off_message = f"""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。"""

    return Dungeon(
        name="地下城.训猎人训练场",
        stages=[
            stage_training_ground,
        ],
    )
