"""地下城生成流水线共用定义：数据模型与 LLM 工具配置"""

from typing import Final, List, final
from pydantic import BaseModel
from ..deepseek import ToolDefinition, ToolFunction


####################################################################################################################################
@final
class DungeonPremiseData(BaseModel):
    """Step 1 中间数据：地下城名称、整体前提描写与场景数量。"""

    dungeon_name: str = ""
    premise: str = ""
    stage_count: int = 2


####################################################################################################################################
@final
class DungeonStageData(BaseModel):
    """Step 2 中间数据：单个战斗场景的名称、标识、环境描写与角色种类数量。"""

    stage_name: str = ""
    profile_name: str = ""
    profile: str = ""
    actor_count: int = 1


####################################################################################################################################
@final
class DungeonStagesData(BaseModel):
    """Step 2 中间数据集合：地下城的全部场景列表。"""

    dungeon_name: str = ""
    premise: str = ""
    stages: List[DungeonStageData] = []


####################################################################################################################################
@final
class DungeonActorBlueprint(BaseModel):
    """地下城怪物实体创建所需的原始字段。供 assemble_dungeon_system 使用。"""

    actor_name: str = ""
    character_sheet_name: str = ""
    profile: str = ""
    base_body: str = ""


####################################################################################################################################
@final
class DungeonStageBlueprint(BaseModel):
    """地下城单个场景实体创建所需的原始字段（包含配对的怪物蓝图）。供 assemble_dungeon_system 使用。"""

    stage_name: str = ""
    profile_name: str = ""
    profile: str = ""
    actors: List[DungeonActorBlueprint] = []
    image_url: str = ""


####################################################################################################################################
@final
class DungeonBlueprint(BaseModel):
    """地下城完整蓝图，承载 Steps 1-3 的全部产出。供 assemble_dungeon_system 使用。

    Attributes:
        dungeon_name: 地下城全名，格式为「地下城.XXXX」
        premise: 地下城整体前提描述
        stages: 已完整配对（场景+怪物）的场景蓝图列表
        image_url: 封面图片 URL，Step 3 写入时为空，由 IllustrateDungeonActionSystem 填充
    """

    dungeon_name: str = ""
    premise: str = ""
    stages: List[DungeonStageBlueprint] = []
    image_url: str = ""


####################################################################################################################################
# Step 1 工具定义
####################################################################################################################################
PREMISE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="record_dungeon_premise",
        description="记录地下城的名称、整体前提写照与场景数量。",
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "地下城全名，采用「地下城.XXXX」命名格式，体现其核心特征",
                },
                "premise": {
                    "type": "string",
                    "description": "该地下城的整体前提写照，100-200字，聚焦感官与情境层面的直观细节，避免直接点出具体角色身份/阵营名称与威胁评价性词汇",
                },
                "stage_count": {
                    "type": "integer",
                    "enum": [2, 3],
                    "description": "该地下城应包含的战斗场景数量，依规模与层次丰富程度选择",
                },
            },
            "required": ["name", "premise", "stage_count"],
        },
    )
)

READ_PREMISE_FILE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="read_premise_file",
        description="读取已写入磁盘的地下城前提中间文件，返回其 JSON 内容。",
        parameters={
            "type": "object",
            "properties": {
                "dungeon_name": {
                    "type": "string",
                    "description": "地下城全名，与 record_dungeon_premise 中填写的 name 字段一致",
                },
            },
            "required": ["dungeon_name"],
        },
    )
)


####################################################################################################################################
# Step 2 工具定义
####################################################################################################################################
READ_STAGES_FILE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="read_stages_file",
        description="读取已写入磁盘的地下城场景中间文件，返回其 JSON 内容。",
        parameters={
            "type": "object",
            "properties": {
                "dungeon_name": {
                    "type": "string",
                    "description": "地下城全名，与 record_dungeon_stages 中填写的 dungeon_name 字段一致",
                },
            },
            "required": ["dungeon_name"],
        },
    )
)


def build_stages_tool(stage_count: int) -> ToolDefinition:
    """动态构建 record_dungeon_stages 工具定义，将 minItems/maxItems 约束绑定到 stage_count。"""
    return ToolDefinition(
        function=ToolFunction(
            name="record_dungeon_stages",
            description=f"记录地下城全部 {stage_count} 个战斗场景的名称、英文标识、环境描写与角色种类数量。",
            parameters={
                "type": "object",
                "properties": {
                    "dungeon_name": {
                        "type": "string",
                        "description": "地下城全名，与 Step 1 premise 文件中的 dungeon_name 一致",
                    },
                    "stages": {
                        "type": "array",
                        "minItems": stage_count,
                        "maxItems": stage_count,
                        "items": {
                            "type": "object",
                            "properties": {
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
                                    "enum": [1, 2],
                                    "description": "该场景内出现的角色种类数量；入口区域为 1，深处场景可为 2",
                                },
                            },
                            "required": [
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
