from ..models import (
    WorldSystem,
    DungeonGenerationComponent,
    ComponentSerialization,
    RPG_SYSTEM_RULES,
)
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
)
from ..models.entity_factory import (
    create_world_system,
)
from typing import Final


_DUNGEON_GENERATION_ROLE_RULES: Final[
    str
] = """## 生态底色规范

「地下城」是独立副本战役，非地理概念，其形态不限，可呈任意形态。

生成地下城时，须从游戏设定的六大生态区域中选取**一个**作为本次地下城的环境底色：

- **沙漠残垣**：古代聚落遗迹，风沙磨蚀的断壁残垣与半掩石板基址
- **地上洞穴与山岩**：红色砂岩山地中互通的洞穴迷宫、天然石桥与竖向天井
- **地下暗河**：深层竖井下方的宽阔暗河道、钟乳石林与古代石堤码头遗迹
- **冰川**：西北冰峰内部的迷宫冰洞、幽蓝裂缝与冻结于冰层中的发光物
- **火山**：东侧岩浆裂谷、黑色火山岩地表、硫磺结晶与温泉地带
- **绿洲**：沙丘环绕的清澈湖泊、湿润岩岸与不断涌出的泉眼区域

所选生态决定地下城与各场景的命名倾向、感官氛围与生物习性；后续所有步骤须以此为底色严格展开，禁止跨生态混搭（除非选取的区域本身存在生态交界地带）。

## 环境描写规范

所有环境文本（生态环境、场景 profile）只描述「这里有什么」，聚焦感官层面：
- 地形结构与光照、温湿度等直观感受
- 植被、土质、水文等自然要素
- 动物活动留下的痕迹（足迹、爪痕、粪便、巢穴碎片、骨骸），不直接点名生物
- 气味、声音等环境线索

## 场景层次规范

多个战斗场景须从入口到最深处呈递进感：
- 入口场景：相对开阔，生物活动痕迹疏散
- 深处场景：空间压迫，生物活动痕迹密集且强烈
- 中间场景：深度与复杂度介于入口与深处之间，逐步递进

## 怪物字段规范

- **actor_name**：采用「怪物.XXXX」格式，XXXX 体现该生物的特征
- **character_sheet_name**：角色英文标识，snake_case 格式（如 bone_crawler、mist_spirit）
- **profile**：第一人称 AI 扮演描述，50-100字，描述性格、行为倾向、与环境的关系
  - 禁忌：不出现战斗数值、技能名称、等级等游戏机制词汇
- **base_body**：第三人称外观描述，30-60字，描述形态、材质、动态特征
  - 禁忌：不出现战斗数值、技能名称、等级等游戏机制词汇
- 同场景有多个生物时，须在形态类型、活动层高、觅食策略上有所区别，避免重复"""


def create_dungeon_generation() -> WorldSystem:
    """
    创建地下城图片生成系统。

    该系统负责在进入地下城时，通过文生图 AI 为地下城及其房间生成场景图片。

    Returns:
        WorldSystem: 配置完成的地下城图片生成系统实例
    """

    world_system = create_world_system(
        name="世界系统.地下城生成系统",
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        role_rules=_DUNGEON_GENERATION_ROLE_RULES,
    )

    # 配置组件
    world_system.components = [
        ComponentSerialization(
            name=DungeonGenerationComponent.__name__,
            data=DungeonGenerationComponent(name=world_system.name).model_dump(),
        )
    ]

    # 返回配置完成的世界系统
    return world_system
