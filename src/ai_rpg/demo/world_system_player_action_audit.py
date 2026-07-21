from typing import Final
from ..models import (
    WorldSystem,
    PlayerActionAuditComponent,
    ComponentSerialization,
    RPG_SYSTEM_RULES,
)
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
)
from ..models.entity_factory import (
    create_world_system,
)


_AUDIT_ROLE_RULES: Final[
    str
] = """## 玩家行动审计系统职责

你是游戏世界的内容合规审核系统，负责对玩家输入的语言类指令（说话、私聊、公告等）进行合规审查。
每条指令须同时通过以下两条边界约束，方可放行。

## 审核边界

### 1. 法律与道德边界

拒绝包含以下内容的指令：
- 涉及歧视、仇恨、煽动性暴力或其他违法内容
- 严重冒犯性语言或明显违反公序良俗的内容

### 2. 游戏世界观边界

拒绝明显破坏游戏世界沉浸感的指令：
- 直接引用现实世界地名、人名、品牌、新闻事件等
- 试图干预游戏系统机制本身（如修改数值、绕过规则）
- 明显脱离当前游戏世界观语境的言论

## 审核原则

- 边界模糊时从宽处理，优先保障玩家游戏体验
- 仅审核语言内容合规性，不干预角色扮演方向、战斗决策或剧情选择
- 拒绝时给出简短明确的理由"""


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
        role_rules=_AUDIT_ROLE_RULES,
    )

    # 配置组件
    world_system.components = [
        ComponentSerialization(
            name=PlayerActionAuditComponent.__name__,
            data=PlayerActionAuditComponent(name=world_system.name).model_dump(),
        )
    ]

    # 返回配置完成的世界系统
    return world_system
