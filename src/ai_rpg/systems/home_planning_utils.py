"""家园规划系统共享工具模块。

提供 HomeNpcPlanSystem 与 HomePlayerContextSystem 共用的：
  - ActionPlanResponse：行动规划响应数据模型
  - _PLAYER_ACTIVE_ACTION_TYPES：玩家主动行动类型常量
  - _format_mind_notification：内心活动通知格式化
  - _build_action_planning_prompt：完整版行动规划提示词构建
  - _build_compressed_planning_prompt：压缩版行动规划提示词构建
  - is_player_active：判断玩家本轮是否有主动行动
"""

from typing import Any, Dict, Final, List, Optional
from pydantic import BaseModel, field_validator
from ..models import (
    AnnounceAction,
    SpeakAction,
    WhisperAction,
    TransStageAction,
    EquipItemAction,
)
from ..game import TCGGame

# 玩家「主动行动」对应的 Action 组件类型集合。
# 当任一玩家持有其中任意类型时，视为本轮「有主动行动」，NPC 将进入待命模式。
# 新增/删除行动类型时只在此处修改，其余判断逻辑均引用此常量。
_PLAYER_ACTIVE_ACTION_TYPES: Final = (
    SpeakAction,
    WhisperAction,
    AnnounceAction,
    TransStageAction,
    EquipItemAction,
)


#######################################################################################################################################
def _format_mind_notification(actor_name: str, mind_content: str) -> str:
    """格式化内心活动通知消息。

    Args:
        actor_name: 角色名称
        mind_content: 内心活动内容

    Returns:
        格式化后的通知消息
    """
    return f"# {actor_name} 内心活动: {mind_content}"


#######################################################################################################################################
class ActionPlanResponse(BaseModel):
    """角色行动规划响应数据模型。

    用于解析和验证 AI 返回的角色行动决策 JSON 数据，
    确保响应结构符合预期格式并包含所有必要的行动信息。

    Attributes:
        mind: 内心独白
        query: 数据库检索关键词
        inspect_self: 查阅自身背包与属性（true 时触发 InspectSelfActionSystem）
        equip_weapon: 装备武器槽的物品全名（None 不更换；"" 脱掉）
        equip_armor: 装备套装槽的物品全名（None 不更换；"" 脱掉）
        equip_accessory: 装备饰品槽的物品全名（None 不更换；"" 脱掉）
        speak: 说话行动（目标角色名 -> 内容）
        whisper: 耳语行动（目标角色名 -> 内容）
        announce: 公开宣布
        trans_stage: 移动目标场景名
    """

    mind: str = ""
    query: str = ""
    inspect_self: bool = False
    equip_weapon: Optional[str] = None
    equip_armor: Optional[str] = None
    equip_accessory: Optional[str] = None
    speak: Dict[str, str] = {}
    whisper: Dict[str, str] = {}
    announce: str = ""
    trans_stage: str = ""

    @field_validator("speak", "whisper", mode="before")
    @classmethod
    def _coerce_dict_none(cls, v: Any) -> Any:
        return v if v is not None else {}

    @field_validator("announce", "trans_stage", mode="before")
    @classmethod
    def _coerce_str_none(cls, v: Any) -> Any:
        return v if v is not None else ""


#######################################################################################################################################
def _build_action_planning_prompt(
    current_stage: str,
    current_stage_narration: str,
    other_actors_appearances: Dict[str, str],
    available_home_stages: List[str],
    planning_turn_index: int,
) -> str:
    """构建角色行动规划提示词（完整版，含所有行动类型）。

    包含：query、inspect_self、speak、whisper、announce、equip_weapon/equip_armor/equip_accessory、trans_stage。

    Args:
        current_stage: 场景名称
        current_stage_narration: 场景环境描述
        other_actors_appearances: 其他角色的外观（角色名 -> 外观）
        available_home_stages: 可前往的场景列表
        planning_turn_index: 全局家园规划回合编号

    Returns:
        完整的行动规划提示词
    """
    # 场景内角色外观描述
    other_actors_appearance_info = []
    for actor_name, appearance in other_actors_appearances.items():
        other_actors_appearance_info.append(f"{actor_name}: {appearance}")
    if len(other_actors_appearance_info) == 0:
        other_actors_appearance_info.append("无")

    return f"""# 决定你要做什么，以JSON格式输出。

## 当前回合: {planning_turn_index}

## 你所在场景信息

{current_stage} | {current_stage_narration}

可移动至: {", ".join(available_home_stages) if len(available_home_stages) > 0 else "无"}

## 本场景内其他角色

{"\n".join(other_actors_appearance_info)}

## 核心规则

1. **每回合行动结构**

```
每回合结构：
├─ mind [必填] - 内心独白/思考
├─ 向内查询 [可叠加，互不干扰]
│   ├─ query        - 检索外部知识库（可选）
│   └─ inspect_self - 查阅自身背包与属性（可选）
└─ 主要行动 [每轮至多选一类，与向内查询互斥]
   ├─ A. 对外交流（三选一）
   │   ├─ speak
   │   ├─ whisper
   │   └─ announce
   ├─ B. 装备操作（三槽可同轮并用）
   │   └─ equip_weapon / equip_armor / equip_accessory
   └─ C. trans_stage - 移动场景
```

> `query` / `inspect_self` 可同时使用，来源不同互不干扰。
> 向内查询与主要行动**不能同轮并用**：若本轮执行主要行动（A/B/C 任意一类），则不填 query / inspect_self。

2. **第一人称视角**  
   所有行动和思考必须以第一人称进行。

3. **知识库检索** (`query`)
   - System prompt 是信息目录，需要详细信息时用 query 向外部数据库检索，结果会添加到下一轮 context

4. **自我审视** (`inspect_self`)
   - 设为 `true` 时，系统将把你的背包物品与当前战斗属性注入到下一轮 context
   - 适合在不确定自身装备或状态时使用；不需要填写任何额外参数
   - 可与 `query` 同时使用

5. **对外交流** (`speak` / `whisper` / `announce`) - 三种方式的区别
   - `speak`：对当前场景内指定角色说话（公开，场景内所有人都能听到）
   - `whisper`：对指定角色耳语（私密，只有你和对方知道）
   - `announce`：向所有家园场景发布公告（广播，所有家园场景的角色都能听到）

   **约束**：三种方式每轮只选其一；只能使用 context 中已有的信息；本轮使用对外交流时，query / inspect_self 留空。

6. **装备操作** (`equip_weapon` / `equip_armor` / `equip_accessory`)
   - 三个装备槽**可在同一轮并用**，不操作的槽位填 `null`
   - 填入背包物品精确全名 → 装备该槽；填写 `""` → 脱掉该槽；填 `null` → 不更换
   - **装备分两轮完成**：第一轮用 `inspect_self` 查阅背包确认物品全名，第二轮再执行 `equip_*`；不可在同一轮同时使用 `inspect_self` 和 `equip_*`
   - 本轮使用装备操作时，query / inspect_self 留空

7. **场景移动** (`trans_stage`)
   - 填写目标场景全名（从"可移动至"列表选择）

8. **严格禁止虚构**：`mind`/`speak`/`whisper` 均只能基于 context 中已有的信息。禁止在任何字段中捏造其他角色的动作、反应或对话，禁止虚构 context 中未记录的事件。`mind` 只写你自己的思考，不得描述他人行为。

## 输出格式(JSON)

```json
{{
  "mind": "内心独白",
  "query": "检索关键词",
  "inspect_self": false,
  "equip_weapon": null,
  "equip_armor": null,
  "equip_accessory": null,
  "speak": {{
    "角色全名": "说话内容"
  }},
  "whisper": {{
    "角色全名": "耳语内容"
  }},
  "announce": "公开宣布内容",
  "trans_stage": "移动目标场景全名"
}}
```

**约束规则**：

- 严格按上述JSON格式输出你的行动决策
- 所有字段名不可更改
- `speak` / `whisper` 不使用时填 `{{}}`（空对象），`announce` / `trans_stage` 不使用时填 `""`（空字符串）；**这四个字段禁止填 `null`**"""


#######################################################################################################################################
def _build_compressed_planning_prompt(
    current_stage: str,
    current_stage_narration: str,
    other_actors_appearances: Dict[str, str],
    available_home_stages: List[str],
    planning_turn_index: int,
) -> str:
    """构建角色行动规划提示词（压缩版，仅保留动态上下文）。

    仅包含每轮变化的感知信息（回合/场景/角色），省略静态规则与格式说明，
    用于写入对话历史，减少后续推理时的重复 token 消耗。

    Args:
        current_stage: 场景名称
        current_stage_narration: 场景环境描述
        other_actors_appearances: 其他角色的外观（角色名 -> 外观）
        available_home_stages: 可前往的场景列表
        planning_turn_index: 全局家园规划回合编号

    Returns:
        压缩版行动规划提示词
    """
    other_actors_appearance_info = []
    for actor_name, appearance in other_actors_appearances.items():
        other_actors_appearance_info.append(f"{actor_name}: {appearance}")
    if not other_actors_appearance_info:
        other_actors_appearance_info.append("无")

    return f"""# 回合 {planning_turn_index} 场景感知

## 场景: {current_stage} | {current_stage_narration}

## 可移动至: {", ".join(available_home_stages) if available_home_stages else "无"}

## 本场景其他角色

{"\n".join(other_actors_appearance_info)}

> 请以JSON格式输出你的行动决策。"""


#######################################################################################################################################
def is_player_active(game: TCGGame) -> bool:
    """判断本轮玩家是否具有主动行动。

    玩家持有 _PLAYER_ACTIVE_ACTION_TYPES 中任意类型的组件时，视为本轮有主动行动。
    供 HomeNpcPlanSystem 等系统直接调用，无需感知内部实现细节。

    Args:
        game: 游戏实例

    Returns:
        玩家持有主动行动组件则返回 True；玩家不存在时返回 False
    """
    player_entity = game.get_player_entity()
    if player_entity is None:
        return False
    return any(
        player_entity.has(action_type) for action_type in _PLAYER_ACTIVE_ACTION_TYPES
    )
