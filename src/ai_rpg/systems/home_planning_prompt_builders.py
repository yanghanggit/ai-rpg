"""家园规划系统共享工具模块。"""

from typing import Any, Dict, List, Set

from pydantic import BaseModel, field_validator

from ..entitas import Entity, Matcher
from ..game import DBGGame
from ..game.rpg_actor_appearances import get_actor_appearances_in_stage
from ..models import HomeComponent


#######################################################################################################################################
def format_mind_notification(actor_name: str, mind_content: str) -> str:
    """格式化内心活动通知消息。"""
    return f"# {actor_name} 内心活动: {mind_content}"


#######################################################################################################################################
class ActionPlanResponse(BaseModel):
    """角色行动规划响应数据模型。"""

    mind: str = ""
    query: str = ""
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
def build_action_planning_prompt(
    current_stage: str,
    current_stage_narration: str,
    other_actors_appearances: Dict[str, str],
    available_home_stages: List[str],
) -> str:
    """构建角色行动规划提示词（完整版，含所有行动类型）。"""

    # 场景内角色外观描述
    other_actors_appearance_info = []
    for actor_name, appearance in other_actors_appearances.items():
        other_actors_appearance_info.append(f"{actor_name}: {appearance}")

    # 如果场景内没有其他角色，则显示"无"
    if len(other_actors_appearance_info) == 0:
        other_actors_appearance_info.append("无")

    return f"""# 决定你要做什么，以JSON格式输出。

## 你所在场景信息

{current_stage} | {current_stage_narration}

可移动至: {", ".join(available_home_stages) if len(available_home_stages) > 0 else "无"}

## 本场景内其他角色

{"\n".join(other_actors_appearance_info)}

## 行动规则

- `mind`（必填）：第一人称内心独白。只写自身思考，禁止捏造他人动作、反应或对话，禁止虚构 context 中未记录的事件。
- `query`（可选）：从外部知识库检索信息。可与任何行动并用。
- `speak` / `whisper` / `announce`（至多选一）：speak 对场景内角色公开说话，whisper 私密耳语，announce 全家园广播。
- `trans_stage`：移动至目标场景（从"可移动至"列表选择）。与 speak / whisper / announce 互斥。

## 输出格式

严格按以下 JSON 格式输出，字段名不可更改。不使用的字段：speak / whisper 填 `{{}}`，其余填 `""`，禁止 `null`。

```json
{{
  "mind": "...",
  "query": "...",
  "speak": {{"角色全名": "..."}},
  "whisper": {{"角色全名": "..."}},
  "announce": "...",
  "trans_stage": "..."
}}
```"""


#######################################################################################################################################
def build_condensed_planning_prompt(
    current_stage: str,
    current_stage_narration: str,
    other_actors_appearances: Dict[str, str],
    available_home_stages: List[str],
) -> str:
    """构建角色行动规划提示词（精简版，仅保留动态上下文）。"""
    other_actors_appearance_info = []
    for actor_name, appearance in other_actors_appearances.items():
        other_actors_appearance_info.append(f"{actor_name}: {appearance}")
    if not other_actors_appearance_info:
        other_actors_appearance_info.append("无")

    return f"""# 场景感知

## 场景: {current_stage} | {current_stage_narration}

## 可移动至: {", ".join(available_home_stages) if available_home_stages else "无"}

## 本场景其他角色

{"\n".join(other_actors_appearance_info)}

> 请以JSON格式输出你的行动决策。"""


#######################################################################################################################################
def get_other_actors_appearances(
    game: DBGGame, actor_entity: Entity, current_stage: Entity
) -> Dict[str, str]:
    """获取当前场景内除自身以外的所有角色外观描述。"""
    appearances = get_actor_appearances_in_stage(game, current_stage)
    appearances.pop(actor_entity.name, None)
    return appearances


#######################################################################################################################################
def get_available_home_stages(
    game: DBGGame, actor_entity: Entity, current_stage: Entity
) -> Set[Entity]:
    """获取玩家可前往的家园场景集合（排除当前场景）。"""
    home_stage_entities = game.get_group(
        Matcher(all_of=[HomeComponent])
    ).entities.copy()
    home_stage_entities.discard(current_stage)
    return home_stage_entities
