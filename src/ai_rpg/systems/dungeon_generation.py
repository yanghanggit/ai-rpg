"""副本生成流水线共用定义：数据模型与 LLM 工具配置"""

from typing import Final, List, Literal, final
from pydantic import BaseModel
from ..deepseek import ToolDefinition, ToolFunction


####################################################################################################################################
@final
class DungeonActorBlueprint(BaseModel):
    """副本怪物实体创建所需的原始字段。供 assemble_dungeon_system 使用。"""

    actor_name: str = ""
    character_sheet_name: str = ""
    profile: str = ""
    base_body: str = ""


####################################################################################################################################
@final
class DungeonStageBlueprint(BaseModel):
    """副本单个场景实体创建所需的原始字段（包含配对的怪物蓝图）。供 assemble_dungeon_system 使用。"""

    room_type: Literal["entry", "combat"]  # 房间类型
    stage_name: str = ""
    profile_name: str = ""
    profile: str = ""
    actors: List[DungeonActorBlueprint] = []
    image_url: str = ""


####################################################################################################################################
@final
class DungeonBlueprint(BaseModel):
    """副本完整蓝图，承载 Steps 1-3 的全部产出。供 assemble_dungeon_system 使用。"""

    dungeon_name: str = ""
    profile: str = ""
    stages: List[DungeonStageBlueprint] = []
    image_url: str = ""


####################################################################################################################################
# Step 3 工具定义
####################################################################################################################################
ACTOR_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="record_dungeon_actor",
        description="记录该场景中一个怪物的全部设定字段。",
        parameters={
            "type": "object",
            "properties": {
                "actor_name": {
                    "type": "string",
                    "description": "角色全名，采用「怪物.XXXX」格式，XXXX 体现该角色的特征",
                },
                "character_sheet_name": {
                    "type": "string",
                    "description": "角色英文标识，snake_case 格式（如 bone_crawler、mist_spirit）",
                },
                "profile": {
                    "type": "string",
                    "description": "第一人称 AI 扮演描述，50-100字，描述该角色的性格、行为倾向、与所处场景的关系；禁止出现战斗数值、技能名称、等级等游戏机制词汇",
                },
                "base_body": {
                    "type": "string",
                    "description": "第三人称外观描述，30-60字，描述该角色的外观、材质、动态特征；禁止出现战斗数值、技能名称、等级等游戏机制词汇",
                },
            },
            "required": ["actor_name", "character_sheet_name", "profile", "base_body"],
        },
    )
)
