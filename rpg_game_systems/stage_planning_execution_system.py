from entitas import Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from components.components import (
    StageComponent,
    PlanningFlagComponent,
    AgentPingFlagComponent,
    KickOffFlagComponent,
    StageStaticFlagComponent,
)
from components.actions import (
    StageNarrationAction,
    StageTagAction,
    TagAction,
)
from agent.agent_response_handler import AgentResponseHandler
from game.rpg_game_context import RPGGameContext
from loguru import logger
from typing import Dict, List, final
import rpg_game_systems.action_component_utils
import rpg_game_systems.prompt_utils
from agent.agent_request_handler import (
    AgentRequestHandler,
)
from game.rpg_game import RPGGame
import rpg_game_systems.stage_entity_utils
import rpg_game_systems.task_request_utils


###############################################################################################################################################
def _generate_stage_plan_prompt(
    actor_appearance_mapping: Dict[str, str],
) -> str:

    # 组织生成角色外观描述
    actor_appearance_mapping_prompt: List[str] = []
    for actor_name, actor_appearance in actor_appearance_mapping.items():
        actor_appearance_mapping_prompt.append(
            f"""### {actor_name}
角色外观:{actor_appearance}"""
        )

    if len(actor_appearance_mapping_prompt) == 0:
        actor_appearance_mapping_prompt.append("无任何角色。")

    # 最终生成
    return f"""# 请制定你的计划({rpg_game_systems.prompt_utils.GeneralPromptTag.STAGE_PLAN_PROMPT_TAG})
规则见 游戏流程 - 制定计划

## 场景内的角色
{"\n".join(actor_appearance_mapping_prompt)}

{rpg_game_systems.prompt_utils.generate_stage_narration_prompt()}

## 输出要求
- 请遵循 输出格式指南。
- 返回结果 至少 包含 {StageNarrationAction.__name__} 和 {TagAction.__name__}。"""


#######################################################################################################################################
@final
class StagePlanningExecutionSystem(ExecuteProcessor):

    @override
    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        await self._execute_stage_tasks()
        # 保底加一个行为？
        self._ensure_stage_actions()

    #######################################################################################################################################
    async def _execute_stage_tasks(self) -> None:

        # step1: 添加任务
        tasks: Dict[str, AgentRequestHandler] = {}
        self._populate_agent_tasks(tasks)

        # step2: 并行执行requests
        if len(tasks) == 0:
            return

        await rpg_game_systems.task_request_utils.gather(
            [task for task in tasks.values()]
        )

        # step3: 处理结果
        self._handle_agent_requests(tasks)

        # step: 习惯性清空
        tasks.clear()

    #######################################################################################################################################
    def _handle_agent_requests(
        self, agent_requests_map: Dict[str, AgentRequestHandler]
    ) -> None:

        for stage_name, agent_request in agent_requests_map.items():

            stage_entity = self._context.get_stage_entity(stage_name)
            assert (
                stage_entity is not None
            ), f"StagePlanningSystem: stage_entity is None, {stage_name}"
            if stage_entity is None:
                continue

            response_handler = AgentResponseHandler(
                stage_name, agent_request.response_content
            )

            is_action_added = rpg_game_systems.action_component_utils.add_stage_actions(
                self._context,
                stage_entity,
                response_handler,
            )

            if not is_action_added:
                logger.warning("StagePlanningSystem: action_add_result is False.")
                self._context.agent_system.discard_last_human_ai_conversation(
                    agent_request.agent_name
                )
                continue

            rpg_game_systems.stage_entity_utils.apply_stage_narration(
                self._context, response_handler
            )

    #######################################################################################################################################
    def _populate_agent_tasks(
        self, requested_agent_tasks: Dict[str, AgentRequestHandler]
    ) -> None:
        requested_agent_tasks.clear()
        stage_entities = self._context.get_group(
            Matcher(
                all_of=[
                    StageComponent,
                    PlanningFlagComponent,
                    AgentPingFlagComponent,
                    KickOffFlagComponent,
                ],
                none_of=[StageStaticFlagComponent],
            )
        ).entities
        for stage_entity in stage_entities:
            agent = self._context.safe_get_agent(stage_entity)
            requested_agent_tasks[agent.name] = (
                AgentRequestHandler.create_with_full_context(
                    agent,
                    _generate_stage_plan_prompt(
                        self._context.retrieve_stage_actor_appearance(stage_entity),
                    ),
                )
            )

    #######################################################################################################################################
    def _ensure_stage_actions(self) -> None:

        stage_entities = self._context.get_group(
            Matcher(
                all_of=[
                    StageComponent,
                    PlanningFlagComponent,
                    AgentPingFlagComponent,
                    KickOffFlagComponent,
                ]
            )
        ).entities

        for stage_entity in stage_entities:

            stage_name = stage_entity.get(StageComponent).name
            if not stage_entity.has(StageNarrationAction):
                logger.warning(
                    f"StagePlanningSystem: add StageNarrateAction = {stage_name}"
                )

                narrate = (
                    rpg_game_systems.stage_entity_utils.extract_current_stage_narrative(
                        self._context, stage_entity
                    )
                )

                stage_entity.replace(
                    StageNarrationAction,
                    stage_name,
                    [narrate],
                )

            if not stage_entity.has(StageTagAction):
                stage_entity.replace(StageTagAction, stage_name, [])


#######################################################################################################################################
