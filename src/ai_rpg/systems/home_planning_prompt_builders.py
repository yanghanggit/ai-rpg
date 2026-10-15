"""家园规划系统共享模块：玩家 / NPC 行动规划共用的场景上下文与提示词。"""

from dataclasses import dataclass
from typing import Dict, List

from ..entitas import Entity, Matcher
from ..game import DBGGame
from ..game.rpg_actor_appearances import get_actor_appearances_in_stage
from ..game.rpg_stage_environment import get_stage_environment
from ..models import HomeComponent
from ..utils import prompt_builder


#######################################################################################################################################
@dataclass(frozen=True)
class PlanningContext:
    """行动规划所需的场景上下文信息。"""

    stage_name: str
    stage_narrative: str
    other_actors_appearances: Dict[str, str]
    available_stage_names: List[str]


#######################################################################################################################################
def build_planning_context(game: DBGGame, entity: Entity) -> PlanningContext:
    """收集角色行动规划所需的全部场景上下文。"""

    current_stage = game.resolve_stage_entity(entity)
    assert current_stage is not None, "当前角色所在的场景不存在"

    # 当前场景内除自身以外的所有角色外观
    other_actors_appearances = get_actor_appearances_in_stage(game, current_stage)
    other_actors_appearances.pop(entity.name, None)

    # 可前往的家园场景集合（排除当前场景）
    available_home_stages = game.get_group(
        Matcher(all_of=[HomeComponent])
    ).entities.copy()

    # 排除当前场景，得到可前往的家园场景集合
    available_home_stages.discard(current_stage)

    return PlanningContext(
        stage_name=current_stage.name,
        # 环境叙事为决策补充信息，缺失时降级为占位文案
        stage_narrative=get_stage_environment(current_stage),
        other_actors_appearances=other_actors_appearances,
        available_stage_names=sorted(e.name for e in available_home_stages),
    )


#######################################################################################################################################
@prompt_builder
def build_action_planning_tool_prompt(ctx: PlanningContext) -> str:
    """构建角色行动规划提示词（工具调用模式）。"""

    other_actors_appearance_info = []
    for actor_name, appearance in ctx.other_actors_appearances.items():
        other_actors_appearance_info.append(f"{actor_name}: {appearance}")

    if not other_actors_appearance_info:
        other_actors_appearance_info.append("无")

    return f"""# 决定你要做什么，通过工具调用提交行动决策。

## 你所在场景信息

{ctx.stage_name} | {ctx.stage_narrative}

可移动至: {", ".join(ctx.available_stage_names) if ctx.available_stage_names else "无"}

## 本场景内其他角色

{"\n".join(other_actors_appearance_info)}

## 行动规则

- 请回顾全局规则中的「实体全名」设定并严格遵守。
- `mind`（必填）：第一人称内心独白，控制在 60 字以内。只写自身思考，禁止捏造他人动作、反应或对话，禁止虚构消息历史中未记录的事件。
- 可选：调用 `query_knowledge_base` 从外部知识库检索信息（可多次），结果返回后再决定行动。
- 最终调用 `submit_action_plan` 提交行动，`action_type` 取值：
  - `none`：不执行主动行动（仅内心独白）
  - `speak` / `whisper` / `announce`：三选一；speak 对场景内角色公开说话，whisper 私密耳语，announce 全家园广播
  - `trans_stage`：移动至目标场景（从"可移动至"列表选择），与 speak / whisper / announce 互斥
- `speak` / `whisper` 需填 `target_messages`（目标角色全名 → 内容）；`announce` 需填 `message`；`trans_stage` 需填 `target_stage_name`。"""


#######################################################################################################################################
