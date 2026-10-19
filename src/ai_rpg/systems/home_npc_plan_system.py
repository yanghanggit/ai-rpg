"""家园 NPC 规划系统：工具调用式规划，最终落成行动组件。"""

import asyncio
from functools import partial
from typing import Any, Dict, Final, List, Optional, final

from loguru import logger
from overrides import override
from pydantic import BaseModel, Field

from ..deepseek import agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game import DBGGame
from ..llm import ToolDefinition, ToolFunction
from ..models import (
    ActorComponent,
    AnnounceAction,
    MindEvent,
    NPCComponent,
    PlanAction,
    PlayerComponent,
    SpeakAction,
    TransStageAction,
    WhisperAction,
)
from ..utils import batch_run_boolean_tasks, prompt_builder
from .home_planning_prompt_builders import (
    build_action_planning_tool_prompt,
    build_planning_context,
)
from .knowledge_query import search_knowledge_base

#######################################################################################################################################
# 工具定义、结果容器与 handler
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
def _build_submit_action_plan_tool(
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
                        "description": "第一人称内心独白，必填，控制在 60 字以内",
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
                            "本轮主动行动类型；none=仅内心独白；speak/whisper/announce 三选一；trans_stage 与前三者互斥"
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
class _PlanResult(BaseModel):
    """submit_action_plan 的收集结果容器。"""

    submitted: bool = False
    mind: str = ""
    action_type: str = "none"
    target_messages: Dict[str, str] = Field(default_factory=dict)
    message: str = ""
    target_stage_name: str = ""


#######################################################################################################################################
async def _handle_query_knowledge_base(game: DBGGame, question: str) -> str:
    """处理 query_knowledge_base 工具调用：线程池内执行同步 RAG 检索。"""
    return await asyncio.to_thread(search_knowledge_base, game, question)


#######################################################################################################################################
def _handle_submit_action_plan(
    result: _PlanResult,
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
@prompt_builder
def _build_mind_notification(actor_name: str, mind_content: str) -> str:
    """格式化内心活动通知消息。"""
    return f"# {actor_name} 内心活动: {mind_content}"


#######################################################################################################################################
@final
class HomeNpcPlanSystem(ReactiveProcessor):
    """家园 NPC 自主行动规划系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlanAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlanAction)
            and entity.has(ActorComponent)
            and entity.has(NPCComponent)
            and not entity.has(PlayerComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        # 每个 NPC 一个结果容器；agent_loop 并发执行，落库阶段串行保证顺序确定
        results: Dict[str, _PlanResult] = {e.name: _PlanResult() for e in entities}
        tasks = [(e.name, self._run_agent_loop(e, results[e.name])) for e in entities]

        await batch_run_boolean_tasks(tasks)

        # 串行落库：写内心独白通知 + 挂载主动行动组件（query 已由工具轨迹写回记忆）
        for entity in entities:
            result = results[entity.name]
            if not result.submitted:
                logger.error(f"HomeNpcPlanSystem: [{entity.name}] 未提交有效行动计划")
                continue
            self._apply_submitted_action(entity, result)

    #######################################################################################################################################
    async def _run_agent_loop(self, entity: Entity, result: _PlanResult) -> bool:
        """驱动单个 NPC 的工具化行动规划（原地写入持久记忆）。"""

        ctx = build_planning_context(self._game, entity)
        prompt = build_action_planning_tool_prompt(ctx)
        submit_tool = _build_submit_action_plan_tool(ctx.available_stage_names)

        ok = await agent_loop(
            name=entity.name,
            input_message=prompt,
            # 原地写：真实工具调用轨迹即持久记忆（"是什么就是什么"）
            messages=self._game.get_agent_memory(entity).messages,
            tools=[QUERY_KNOWLEDGE_BASE_TOOL, submit_tool],
            handlers={
                QUERY_KNOWLEDGE_BASE_TOOL.function.name: partial(
                    _handle_query_knowledge_base, self._game
                ),
                submit_tool.function.name: partial(_handle_submit_action_plan, result),
            },
            terminal_tools=[submit_tool],
            max_rounds=5,
        )

        # agent_loop 直接原地追加 AI 消息（绕过 add_ai_message），需手动同步最新上下文占比
        self._game.sync_latest_context_usage_ratio(entity)

        return bool(ok) and result.submitted

    #######################################################################################################################################
    def _apply_submitted_action(self, entity: Entity, result: _PlanResult) -> None:
        """将提交的行动决策落到 ECS 组件（query 除外，已工具化）。"""

        # 内心独白：仅通知自己
        if result.mind:
            stage_entity = self._game.resolve_stage_entity(entity)
            assert stage_entity is not None, "actor无所在场景是有问题的"
            self._game.notify_entities(
                {entity},
                MindEvent(
                    message=_build_mind_notification(entity.name, result.mind),
                    actor=entity.name,
                    stage=stage_entity.name,
                    content=result.mind,
                ),
            )

        # 主动行动：挂载对应组件，交由下游系统处理
        has_target_messages = isinstance(result.target_messages, dict) and bool(
            result.target_messages
        )
        if result.action_type == "speak" and has_target_messages:
            entity.replace(SpeakAction, entity.name, result.target_messages)
        elif result.action_type == "whisper" and has_target_messages:
            entity.replace(WhisperAction, entity.name, result.target_messages)
        elif result.action_type == "announce" and result.message:
            entity.replace(AnnounceAction, entity.name, result.message)
        elif result.action_type == "trans_stage" and result.target_stage_name:
            entity.replace(TransStageAction, entity.name, result.target_stage_name)
        # action_type == "none" 或 payload 缺失 → 不挂组件


#######################################################################################################################################
