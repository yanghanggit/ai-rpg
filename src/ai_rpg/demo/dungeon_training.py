from .actor_training_dummy import create_training_dummy
from .stage_village import create_training_ground
from ..models import Dungeon, StageType


def create_training_dungeon() -> Dungeon:
    """创建猎人训练场地下城实例

    Returns:
        包含训练场景和可自动修复训练木桩的地下城
    """

    # 创建训练木桩角色
    actor_training_dummy = create_training_dummy()

    # 故意测试将生命值设为1，方便训练时快速击败
    actor_training_dummy.character_stats.hp = 1

    # 设置游戏启动对话, 故意加一条规则让木桩具备不死效果
    actor_training_dummy.kick_off_message = f"""# 游戏启动！告诉我你是谁？请说出你的全名。回答简短(<100字)。

## 重要规则：青木妖心节（固有特性）

你的楠木主干内嵌有来自竹木大妖"建木"的心节，赋予你不死重生的固有能力。

在以下阶段必须生成对应的 status effect：

1. **战斗初始化**：首次报告自身状态时
2. **状态效果评估阶段**：每回合结算完毕评估状态效果时

**生成内容**：

- **name**: "青木妖心节·不死重生"
- **description**: "楠木主干内嵌有建木心节，HP归零时会立即重生，恢复至最大生命值"

**重要**：即使被消耗使用，下次评估时必须重新生成此固有特性。"""

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
