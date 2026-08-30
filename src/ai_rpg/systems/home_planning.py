"""家园规划系统共享模块：场景上下文、提示词、工具定义与 handler。"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Final, List, Optional, Set

from pydantic import BaseModel, Field

from ..deepseek import ToolDefinition, ToolFunction
from ..entitas import Entity, Matcher
from ..game import DBGGame
from ..game.rpg_actor_appearances import get_actor_appearances_in_stage
from ..models import HomeComponent, StageDescriptionComponent
from ..utils import prompt_builder
from .knowledge_query import search_knowledge_base

#######################################################################################################################################
# 工具定义
#######################################################################################################################################
QUERY_KNOWLEDGE_BASE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="query_knowledge_base",
        description="从外部知识库检索信息，结果会返回供你参考后再决定行动，可多次调用。",
        parameters={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "要检索的问题",
                },
            },
            "required": ["question"],
        },
    )
)


#######################################################################################################################################
def build_submit_action_plan_tool(
    available_stage_names: List[str],
) -> ToolDefinition:
    """构建 submit_action_plan 终止工具，target_stage_name 约束为可去家园场景。"""

    target_stage_schema: Dict[str, Any] = {
        "type": "string",
        "description": "trans_stage 时必填：目标家园场景全名",
    }
    if available_stage_names:
        target_stage_schema["enum"] = available_stage_names

    return ToolDefinition(
        function=ToolFunction(
            name="submit_action_plan",
            description="提交最终行动决策，调用后本轮规划结束。",
            parameters={
                "type": "object",
                "properties": {
                    "mind": {
                        "type": "string",
                        "description": "第一人称内心独白，必填",
                    },
                    "action_type": {
                        "type": "string",
                        "enum": [
                            "none",
                            "speak",
                            "whisper",
                            "announce",
                            "trans_stage",
                        ],
                        "description": (
                            "本轮主动行动类型；none=仅内心独白；"
                            "speak/whisper/announce 三选一；trans_stage 与前三者互斥"
                        ),
                    },
                    "target_messages": {
                        "type": "object",
                        "description": "speak/whisper 时必填：{目标角色全名: 消息内容}",
                    },
                    "message": {
                        "type": "string",
                        "description": "announce 时必填",
                    },
                    "target_stage_name": target_stage_schema,
                },
                "required": ["mind", "action_type"],
            },
        )
    )


#######################################################################################################################################
# 结果容器与 handler
#######################################################################################################################################
class PlanResult(BaseModel):
    """submit_action_plan 的收集结果容器。"""

    submitted: bool = False
    mind: str = ""
    action_type: str = "none"
    target_messages: Dict[str, str] = Field(default_factory=dict)
    message: str = ""
    target_stage_name: str = ""


#######################################################################################################################################
async def handle_query_knowledge_base(game: DBGGame, question: str) -> str:
    """处理 query_knowledge_base 工具调用：线程池内执行同步 RAG 检索。"""
    return await asyncio.to_thread(search_knowledge_base, game, question)


#######################################################################################################################################
def handle_submit_action_plan(
    result: PlanResult,
    mind: str,
    action_type: str,
    target_messages: Optional[Dict[str, str]] = None,
    message: Optional[str] = None,
    target_stage_name: Optional[str] = None,
) -> str:
    """处理 submit_action_plan 工具调用：仅收集，落库由系统在 loop 结束后串行执行。"""

    result.mind = mind or ""
    result.action_type = action_type
    result.target_messages = target_messages or {}
    result.message = message or ""
    result.target_stage_name = target_stage_name or ""
    result.submitted = True
    return "行动计划已提交"


#######################################################################################################################################
# 提示词与场景上下文
#######################################################################################################################################
@prompt_builder
def build_mind_notification(actor_name: str, mind_content: str) -> str:
    """格式化内心活动通知消息。"""
    return f"# {actor_name} 内心活动: {mind_content}"


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
    assert current_stage.has(
        StageDescriptionComponent
    ), "场景缺少 StageDescriptionComponent"

    other_actors_appearances = get_other_actors_appearances(game, entity, current_stage)
    available_home_stages = get_available_home_stages(game, entity, current_stage)
    stage_narrative = current_stage.get(StageDescriptionComponent).narrative
    available_stage_names = sorted(e.name for e in available_home_stages)

    return PlanningContext(
        stage_name=current_stage.name,
        stage_narrative=stage_narrative,
        other_actors_appearances=other_actors_appearances,
        available_stage_names=available_stage_names,
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

- `mind`（必填）：第一人称内心独白。只写自身思考，禁止捏造他人动作、反应或对话，禁止虚构消息历史中未记录的事件。
- 可选：调用 `query_knowledge_base` 从外部知识库检索信息（可多次），结果返回后再决定行动。
- 最终调用 `submit_action_plan` 提交行动，`action_type` 取值：
  - `none`：不执行主动行动（仅内心独白）
  - `speak` / `whisper` / `announce`：三选一；speak 对场景内角色公开说话，whisper 私密耳语，announce 全家园广播
  - `trans_stage`：移动至目标场景（从"可移动至"列表选择），与 speak / whisper / announce 互斥
- `speak` / `whisper` 需填 `target_messages`（目标角色全名 → 内容）；`announce` 需填 `message`；`trans_stage` 需填 `target_stage_name`。"""


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
    """获取角色可前往的家园场景集合（排除当前场景）。"""
    home_stage_entities = game.get_group(
        Matcher(all_of=[HomeComponent])
    ).entities.copy()
    home_stage_entities.discard(current_stage)
    return home_stage_entities


#######################################################################################################################################
