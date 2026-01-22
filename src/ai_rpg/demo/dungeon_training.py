from .actor_training_dummy import create_training_dummy
from .stage_village import create_training_ground
from ..models import Dungeon, StageType, UniqueItem


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
    # actor_training_dummy.kick_off_message = (
    #     """# 游戏启动！告诉我你是谁？请说出你的全名。回答简短(<100字)。"""
    # )

    # 给训练木桩添加特殊物品：青木妖心节·不死重生
    actor_training_dummy.items = [
        UniqueItem(
            name="青木妖心节·不死重生",
            uuid="",
            description="建木妖力结晶形成的青木妖心节，嵌入训练木桩的楠木主干深处，赋予其自我修复的妖力循环。",
            count=1,
            affixes=[
                "不死重生: HP归零时立即触发，完全恢复至最大生命值。此效果为固有特性，无法移除。"
            ],
        )
    ]

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
