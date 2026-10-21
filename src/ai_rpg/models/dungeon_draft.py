"""副本生成流水线的中间数据模型。"""

from typing import Final, List, Literal, Optional, final

from pydantic import BaseModel

####################################################################################################################################
# 副本结构的「默认值」——不是不变量。
#
# 未来由 LLM 按自身的创作原则与判断决定房间组合，代码只负责给出默认值与合法边界：
# - 开场房间默认且通常恒为 1（无战斗，纯门口氛围铺垫）；
# - 战斗房间数与每个战斗房间的怪物数可能变化。
#
# 这些默认值只用于运行时构造任务提示词与工具 schema，不写进 demo 的系统提示词，
# 因此调整无需重刷蓝图（python -m scripts.setup_demo）。
DEFAULT_OPENING_ROOM_COUNT: Final[int] = 1  # 默认开场房间数：无战斗，纯门口氛围铺垫
DEFAULT_COMBAT_ROOM_COUNT: Final[int] = 1  # 默认战斗房间数
DEFAULT_MONSTERS_PER_COMBAT_ROOM: Final[int] = 1  # 默认每个战斗房间的怪物数
DEFAULT_DUNGEON_ROOM_COUNT: Final[int] = (
    DEFAULT_OPENING_ROOM_COUNT + DEFAULT_COMBAT_ROOM_COUNT
)  # 默认副本房间总数


####################################################################################################################################
@final
class DungeonGenerationSpec(BaseModel):
    """一次副本生成的显式结构规格（**调测专用**）。

    只由开发入口（`ai-rpg-dbg-agent-game` 的 `generate-dungeon`）写入
    `GenerateDungeonAction.spec`；正式 API 入口（`/api/home/generate_dungeon/v1/`）的
    请求模型不暴露任何对应字段，因此线上无法借此作弊。

    每个字段取 `0` / 空表示「不覆盖，走默认口径」：
    - `room_count`：总房间数（含开场），0 → `DEFAULT_DUNGEON_ROOM_COUNT`；
    - `opening_room_count`：开场房间数，0 → `DEFAULT_OPENING_ROOM_COUNT`；
    - `monsters_per_combat_room`：每个战斗房间的怪物数，0 → `DEFAULT_MONSTERS_PER_COMBAT_ROOM`；
    - `deck_prototype_ids`：怪物牌库的显式原型 id（空 → 怪物自己选）。
    """

    room_count: int = 0
    opening_room_count: int = 0
    monsters_per_combat_room: int = 0
    deck_prototype_ids: List[str] = []

    def resolved_room_count(self) -> int:
        return self.room_count or DEFAULT_DUNGEON_ROOM_COUNT

    def resolved_opening_room_count(self) -> int:
        return self.opening_room_count or DEFAULT_OPENING_ROOM_COUNT

    def resolved_monsters_per_combat_room(self) -> int:
        return self.monsters_per_combat_room or DEFAULT_MONSTERS_PER_COMBAT_ROOM


####################################################################################################################################
def validate_generation_spec(spec: DungeonGenerationSpec) -> Optional[str]:
    """校验结构规格是否自洽；合法返回 None，否则返回可直接展示的错误信息。"""

    if spec.room_count < 0 or spec.opening_room_count < 0:
        return "房间数不能为负"
    if spec.monsters_per_combat_room < 0:
        return "每个战斗房间的怪物数不能为负"

    room_count = spec.resolved_room_count()
    opening_room_count = spec.resolved_opening_room_count()

    if opening_room_count >= room_count:
        return f"开场房间数（{opening_room_count}）必须小于总房间数（{room_count}）：至少要有 1 个战斗房间"
    return None


####################################################################################################################################
@final
class DungeonRoomDraft(BaseModel):
    """单个房间的类型、名称、环境描写与角色种类数量。"""

    room_type: Literal["opening", "combat"]  # 房间类型：opening=开场叙事，combat=战斗
    room_name: str = ""
    profile: str = ""
    actor_count: int = 0  # 角色种类数量（opening 房间固定为 0）


####################################################################################################################################
@final
class DungeonActorDraft(BaseModel):
    """单个怪物及其归属房间。"""

    room_name: str = (
        ""  # 归属房间全名（「房间.XXXX」，与 DungeonRoomDraft.room_name 一致）
    )
    actor_name: str = ""
    profile: str = ""
    base_body: str = ""
    motif: str = (
        ""  # 艺术锚点（母题 / 意象 / 禁忌 / 命名口吻）；随 profile 一同生成，供卡牌等创作取用
    )


####################################################################################################################################
@final
class DungeonDraft(BaseModel):
    """副本生成的中间过程数据。

    挂在 DBGGame 上（与 _world 平级），不落盘；组装完成后由尾部系统清空，
    流程中途断掉即视为放弃。
    """

    directive: str = ""  # 世界导演的副本创作指令
    dungeon_name: str = ""
    profile: str = ""
    room_count: int = (
        DEFAULT_DUNGEON_ROOM_COUNT  # 副本房间总数（未规划结构时取默认值，包含开场房间）
    )
    rooms: List[DungeonRoomDraft] = []
    actors: List[DungeonActorDraft] = []
