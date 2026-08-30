"""家园 NPC 自主行动规划系统。"""

from functools import partial
from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..deepseek import agent_loop, batch_agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game import DBGGame
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
from .home_planning import (
    QUERY_KNOWLEDGE_BASE_TOOL,
    PlanResult,
    build_action_planning_tool_prompt,
    build_mind_notification,
    build_planning_context,
    build_submit_action_plan_tool,
    handle_query_knowledge_base,
    handle_submit_action_plan,
)


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
        results: Dict[str, PlanResult] = {e.name: PlanResult() for e in entities}
        tasks = [(e.name, self._run_agent_loop(e, results[e.name])) for e in entities]

        await batch_agent_loop(tasks)

        # 串行落库：写内心独白通知 + 挂载主动行动组件（query 已由工具轨迹写回记忆）
        for entity in entities:
            result = results[entity.name]
            if not result.submitted:
                logger.error(f"HomeNpcPlanSystem: [{entity.name}] 未提交有效行动计划")
                continue
            self._apply_submitted_action(entity, result)

    #######################################################################################################################################
    async def _run_agent_loop(self, entity: Entity, result: PlanResult) -> bool:
        """驱动单个 NPC 的工具化行动规划（原地写入持久记忆）。"""

        ctx = build_planning_context(self._game, entity)
        prompt = build_action_planning_tool_prompt(ctx)
        submit_tool = build_submit_action_plan_tool(ctx.available_stage_names)

        ok = await agent_loop(
            name=entity.name,
            prompt=prompt,
            # 原地写：真实工具调用轨迹即持久记忆（"是什么就是什么"）
            messages=self._game.get_agent_memory(entity).messages,
            tools=[QUERY_KNOWLEDGE_BASE_TOOL, submit_tool],
            handlers={
                "query_knowledge_base": partial(
                    handle_query_knowledge_base, self._game
                ),
                "submit_action_plan": partial(handle_submit_action_plan, result),
            },
            terminal_tools=[submit_tool],
            max_rounds=5,
        )
        return ok and result.submitted

    #######################################################################################################################################
    def _apply_submitted_action(self, entity: Entity, result: PlanResult) -> None:
        """将提交的行动决策落到 ECS 组件（query 除外，已工具化）。"""

        # 内心独白：仅通知自己
        if result.mind:
            stage_entity = self._game.resolve_stage_entity(entity)
            assert stage_entity is not None, "actor无所在场景是有问题的"
            self._game.notify_entities(
                {entity},
                MindEvent(
                    message=build_mind_notification(entity.name, result.mind),
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
