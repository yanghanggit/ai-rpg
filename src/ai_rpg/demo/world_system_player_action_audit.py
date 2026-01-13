from ..models import (
    WorldSystem,
    PlayerActionAuditComponent,
)
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
    RPG_SYSTEM_RULES,
)
from .entity_factory import (
    create_world_system,
)


def create_player_action_audit() -> WorldSystem:
    """
    创建玩家行动审计系统。

    该系统负责审阅玩家输入的语言类指令，确保指令内容合规：
    1. 不包含法律与道德禁止的内容
    2. 不包含跳出游戏世界观的内容

    Returns:
        WorldSystem: 配置完成的玩家行动审计系统实例
    """

    world_system = create_world_system(
        name="世界系统.玩家行动审计系统",
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    world_system.kick_off_message = """# 游戏启动！你是玩家行动审计系统，负责审查玩家输入的语言类指令。

## 审计标准

**必须拒绝的内容：**
1. 法律与道德禁止的内容：暴力教唆、违法行为、极端言论、歧视性内容、侮辱性语言
2. 破坏游戏世界观的内容：提及现实世界科技（手机、电脑、互联网）、元游戏语言（"我是玩家"、"这是游戏"、"重新开始"）、系统操作（"查看属性"、"保存进度"）

**允许的内容：**
1. 符合游戏世界观的角色互动：对话、探索、战斗、交易等
2. 游戏内合理行为：使用道具、施法、移动、调查环境等
3. 符合角色身份的情绪表达和决策"""

    # 配置组件
    world_system.component = PlayerActionAuditComponent.__name__

    # 返回配置完成的世界系统
    return world_system
