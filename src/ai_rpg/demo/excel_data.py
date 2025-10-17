from typing import final

from pydantic import BaseModel, Field


###############################################################################################################################################
# Excel地牢数据模型
@final
class DungeonExcelData(BaseModel):
    """地牢Excel数据的BaseModel"""

    name: str = Field(default="未命名地牢", description="地牢名称")
    character_sheet_name: str = Field(
        default="default_dungeon", description="角色表名称"
    )
    dungeon_name: str = Field(default="未命名地牢", description="地牢名称")
    kick_off_message: str = Field(default="", description="开始消息")
    type: str = Field(default="Dungeon", description="类型")
    stage_profile: str = Field(
        default="默认地牢描述：一个神秘的地牢，等待冒险者探索。", description="地牢描述"
    )
    actor: str = Field(default="", description="相关角色")


###############################################################################################################################################
# Excel角色数据模型
@final
class ActorExcelData(BaseModel):
    """角色Excel数据的BaseModel"""

    name: str = Field(default="未命名怪物", description="角色名称")
    character_sheet_name: str = Field(
        default="default_monster", description="角色表名称"
    )
    kick_off_message: str = Field(default="", description="开始消息")
    type: str = Field(default="Monster", description="角色类型")
    actor_profile: str = Field(
        default="默认怪物描述：一个神秘的怪物，等待冒险者探索。", description="角色描述"
    )
    appearance: str = Field(default="默认怪物外观：", description="角色外观")


###############################################################################################################################################
# 狼人杀角色Excel数据模型
@final
class WerewolfAppearanceExcelData(BaseModel):
    """狼人杀角色Excel数据的BaseModel"""

    mask: str = Field(default="默认面具", description="面具")
    body_type: str = Field(default="身材高挑", description="身材")
    gender: str = Field(default="男性", description="性别")

######