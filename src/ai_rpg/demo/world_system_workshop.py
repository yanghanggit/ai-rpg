from ..models import (
    WorkshopComponent,
    ComponentSerialization,
)
from .global_settings import RPG_CAMPAIGN_SETTING
from .rpg_system_rules import RPG_SYSTEM_RULES
from .entity_factory import create_world_system
from ..models import WorldSystem
from typing import Final


_WORKSHOP_ROLE_RULES: Final[
    str
] = """## 制造工坊职责

你是游戏世界的制造工坊系统，负责根据玩家提交的材料，创意合成消耗品、装备或时装。
所有生成物品须植根于游戏世界设定，其感官描述、命名风格与材料来源须相互呼应。

## 命名规范

- **消耗品**：采用「消耗品.XXXX」格式，名称体现材料特性与主要用途
- **装备**：采用「装备.XXXX」格式，名称体现材料质地与器械类型
- **时装**：采用「时装.XXXX」格式，名称体现外观风格与材料来源

XXXX 部分简洁有辨识度，避免使用数字后缀（如"消耗品.01"）。

## 描述规范

物品描述须聚焦感官层面，呈现材料来源的痕迹：
- 呈现制成品的视觉特征、气味、质感或使用感受
- 通过描述隐含材料来源（如沙漠草药的气味、冰川矿石的光泽）
- 禁止出现战斗数值、技能名称、属性词语等游戏机制词汇
- 禁止直接指涉游戏逻辑（如"造成 30 点伤害"、"提升攻击力"）

## 世界根植性

游戏世界由六大生态区域构成，合成物品的感官风格应与其核心材料的来源生态呼应：

- **沙漠残垣**：干热、风蚀、古代遗迹的气息
- **地上洞穴与山岩**：矿物、红砂岩、地下潮湿
- **地下暗河**：幽暗水系、磷光、钟乳石
- **冰川**：极寒、冰晶光泽、封存物
- **火山**：硫磺、岩浆矿物、高温烧灼感
- **绿洲**：清水、矿泉、沙漠边缘植物"""


def create_workshop() -> WorldSystem:
    """创建制造工坊世界系统，为 CraftItemActionSystem 提供 LLM context。

    Returns:
        WorldSystem: 配置完成的制造工坊世界系统实例
    """
    world_system = create_world_system(
        name="世界系统.制造工坊",
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        role_rules=_WORKSHOP_ROLE_RULES,
    )

    world_system.components = [
        ComponentSerialization(
            name=WorkshopComponent.__name__,
            data=WorkshopComponent(name=world_system.name).model_dump(),
        )
    ]

    return world_system
