"""副本生成流水线共用定义：数据模型与 LLM 工具配置"""

from typing import Final, List, Literal, final
from pydantic import BaseModel
from ..deepseek import ToolDefinition, ToolFunction


####################################################################################################################################
@final
class DungeonStageData(BaseModel):
    """Step 2 中间数据：单个场景的名称、类型、标识、环境描写与角色种类数量。"""

    room_type: Literal["entry", "combat"]  # 房间类型：entry=叙事入口，combat=战斗
    stage_name: str = ""
    profile_name: str = ""
    profile: str = ""
    actor_count: int = 0  # 角色种类数量（entry 房间固定为 0）


####################################################################################################################################
@final
class DungeonStagesData(BaseModel):
    """Step 2 中间数据集合：副本的全部场景列表。"""

    dungeon_name: str = ""
    profile: str = ""
    stages: List[DungeonStageData] = []


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
# Step 1 工具定义
####################################################################################################################################

####################################################################################################################################
# Step 2 工具定义
####################################################################################################################################
READ_STAGES_FILE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="read_stages_file",
        description="读取已写入磁盘的副本场景中间文件，返回其 JSON 内容。",
        parameters={
            "type": "object",
            "properties": {
                "dungeon_name": {
                    "type": "string",
                    "description": "副本全名，与 record_dungeon_stages 中填写的 dungeon_name 字段一致",
                },
            },
            "required": ["dungeon_name"],
        },
    )
)


def build_stages_tool(dungeon_room_count: int) -> ToolDefinition:
    """动态构建 record_dungeon_stages 工具定义。

    总场景数 = 1 个叙事入口（entry） + dungeon_room_count 个战斗房间（combat）。
    """
    total_stages = 1 + dungeon_room_count
    return ToolDefinition(
        function=ToolFunction(
            name="record_dungeon_stages",
            description=(
                f"记录副本全部 {total_stages} 个场景：首个为叙事入口（entry），"
                f"其余 {dungeon_room_count} 个为战斗房间（combat）。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "dungeon_name": {
                        "type": "string",
                        "description": "副本全名，与 Step 1 profile 文件中的 dungeon_name 一致",
                    },
                    "stages": {
                        "type": "array",
                        "minItems": total_stages,
                        "maxItems": total_stages,
                        "items": {
                            "type": "object",
                            "properties": {
                                "room_type": {
                                    "type": "string",
                                    "enum": ["entry", "combat"],
                                    "description": (
                                        "房间类型：'entry' = 叙事入口房间（无战斗，纯场景氛围描写），"
                                        "'combat' = 战斗房间。第一个场景必须为 'entry'，其余必须为 'combat'"
                                    ),
                                },
                                "stage_name": {
                                    "type": "string",
                                    "description": "场景全名，采用「场景.XXXX」命名格式，体现该局部区域的核心特征，所有场景名称不重复",
                                },
                                "profile_name": {
                                    "type": "string",
                                    "description": "场景英文标识，snake_case 格式（如 forest_edge、deep_pool），所有标识不重复",
                                },
                                "profile": {
                                    "type": "string",
                                    "description": "该场景的感官环境描写，50-100字，只描述「这里有什么」，避免直接点出具体角色身份/阵营名称与威胁评价性词汇",
                                },
                                "actor_count": {
                                    "type": "integer",
                                    "enum": [0, 1, 2],
                                    "description": "角色种类数量。entry 房间填 0；combat 房间入口为 1，深处可为 2",
                                },
                            },
                            "required": [
                                "room_type",
                                "stage_name",
                                "profile_name",
                                "profile",
                                "actor_count",
                            ],
                        },
                    },
                },
                "required": ["dungeon_name", "stages"],
            },
        )
    )


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
