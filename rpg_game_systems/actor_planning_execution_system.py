from entitas import Entity, Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from components.components import (
    ActorComponent,
    PlanningFlagComponent,
    StageGraphComponent,
    PlayerActorFlagComponent,
    AgentPingFlagComponent,
    KickOffDoneFlagComponent,
)
from components.actions import (
    GoToAction,
    TagAction,
)
from agent.agent_response_handler import AgentResponseHandler
from game.rpg_game_context import RPGGameContext
from loguru import logger
from typing import Dict, Set, List, Optional, final
import rpg_game_systems.action_component_utils
import rpg_game_systems.prompt_utils
from agent.agent_request_handler import (
    AgentRequestHandler,
)
from game.rpg_game import RPGGame
from rpg_game_systems.actor_entity_utils import ActorStatusEvaluator
from extended_systems.prop_file import (
    PropFile,
    generate_prop_file_total_prompt,
)
from rpg_models.file_models import PropType
import rpg_game_systems.stage_entity_utils
import rpg_game_systems.task_request_utils


###############################################################################################################################################
def _generate_props_prompt(
    prop_info: Dict[str, List[PropFile]],
    order_keys: List[str] = [
        PropType.TYPE_SPECIAL,
        PropType.TYPE_WEAPON,
        PropType.TYPE_CLOTHES,
        PropType.TYPE_NON_CONSUMABLE_ITEM,
        PropType.TYPE_CONSUMABLE_ITEM,
        PropType.TYPE_SKILL,
    ],
) -> List[str]:

    ret: List[str] = []

    for key in order_keys:
        if key not in prop_info:
            continue

        for prop_file in prop_info[key]:
            ret.append(generate_prop_file_total_prompt(prop_file))

    return ret


###############################################################################################################################################
def _generate_actor_plan_prompt(
    current_stage: str,
    stage_narrate: str,
    stage_graph: Set[str],
    actor_appearance_mapping: Dict[str, str],
    health_description: str,
    actor_props: Dict[str, List[PropFile]],
    current_weapon: Optional[PropFile],
    current_clothes: Optional[PropFile],
) -> str:

    assert current_stage != "", "current_stage is empty"

    # 组织生成角色道具描述
    # health_description *= 100

    # 组织生成角色道具描述
    props_prompt = _generate_props_prompt(actor_props)
    if len(props_prompt) == 0:
        props_prompt.append("无任何道具。")

    # 组织生成角色外观描述
    actor_appearance_mapping_prompt: List[str] = []
    for actor_name, actor_appearance in actor_appearance_mapping.items():
        actor_appearance_mapping_prompt.append(
            f"""### {actor_name}
角色外观:{actor_appearance}"""
        )

    if len(actor_appearance_mapping_prompt) == 0:
        actor_appearance_mapping_prompt.append("无任何角色。")

    #
    if len(stage_graph) == 0:
        stage_graph.add(f"无可去往场景(你不可以执行{GoToAction.__name__})")

    return f"""# 请制定你的计划({rpg_game_systems.prompt_utils.GeneralPromptTag.ACTOR_PLAN_PROMPT_TAG})
规则见 游戏流程 - 制定计划

## 你当前所在的场景
{current_stage}

### 场景描述
{stage_narrate}

### (如从本场景离开)你可以去往的场景，即动作 {GoToAction.__name__} 可以执行的目标场景
{"\n".join(stage_graph)}   

## 场景内的角色
{"\n".join(actor_appearance_mapping_prompt)}

## 你的健康状态
生命值: {health_description}

## 你的全部道具
{"\n".join(props_prompt)}

## 你已经装备的道具
- 武器: {current_weapon is not None and current_weapon.name or "无"}
- 衣服: {current_clothes is not None and current_clothes.name or "无"}

{rpg_game_systems.prompt_utils.generate_equip_action_prompt()}

{rpg_game_systems.prompt_utils.generate_skill_action_prompt(actor_props.get(PropType.TYPE_SKILL, []))}

## 输出要求
- 请遵循 输出格式指南。
- 返回结果 至少 包含 {TagAction.__name__}。"""


#######################################################################################################################################


@final
class ActorPlanningExecutionSystem(ExecuteProcessor):

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
        # step1: 添加任务
        tasks: Dict[str, AgentRequestHandler] = {}
        self._populate_agent_tasks(tasks)

        # step2: 并行执行requests
        if len(tasks) == 0:
            return

        responses = await rpg_game_systems.task_request_utils.gather(
            [task for task in tasks.values()]
        )
        if len(responses) == 0:
            logger.warning(f"ActorPlanningSystem: request_result is empty.")
            return

        self._handle_agent_requests(tasks)
        tasks.clear()

    #######################################################################################################################################
    def _handle_agent_requests(
        self, agent_requests_map: Dict[str, AgentRequestHandler]
    ) -> None:

        for actor_name, agent_request in agent_requests_map.items():

            actor_entity = self._context.get_actor_entity(actor_name)
            assert (
                actor_entity is not None
            ), f"ActorPlanningSystem: entity is None, {actor_name}"

            if actor_entity is None:
                continue

            is_action_added = rpg_game_systems.action_component_utils.add_actor_actions(
                self._context,
                actor_entity,
                AgentResponseHandler(actor_name, agent_request.response_content),
            )

            if not is_action_added:
                logger.warning("ActorPlanningSystem: action_add_result is False.")
                self._context.agent_system.discard_last_human_ai_conversation(
                    agent_request.agent_name
                )
                continue

    #######################################################################################################################################
    def _populate_agent_tasks(
        self, planned_agent_tasks: Dict[str, AgentRequestHandler]
    ) -> None:

        planned_agent_tasks.clear()

        actor_entities = self._context.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                    PlanningFlagComponent,
                    AgentPingFlagComponent,
                    KickOffDoneFlagComponent,
                ],
                none_of=[PlayerActorFlagComponent],
            )
        ).entities
        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            check_self = ActorStatusEvaluator(self._context, actor_entity)
            actor_appearance_mapping = self._context.retrieve_stage_actor_appearance(
                actor_entity
            )
            actor_appearance_mapping.pop(actor_comp.name, None)  # 自己不要

            planned_agent_tasks[actor_comp.name] = (
                AgentRequestHandler.create_with_full_context(
                    self._context.safe_get_agent(actor_entity),
                    _generate_actor_plan_prompt(
                        current_stage=self._retrieve_stage_name(actor_entity),
                        stage_narrate=rpg_game_systems.stage_entity_utils.extract_current_stage_narrative(
                            self._context, actor_entity
                        ),
                        stage_graph=set(self._retrieve_stage_graph(actor_entity)),
                        actor_appearance_mapping=actor_appearance_mapping,
                        health_description=check_self.format_health_info,
                        actor_props=check_self._category_prop_files,
                        current_weapon=check_self._current_weapon,
                        current_clothes=check_self._current_clothes,
                    ),
                )
            )

    #######################################################################################################################################
    def _retrieve_stage_name(self, actor_entity: Entity) -> str:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        assert stage_entity is not None, "stage is None, actor无所在场景是有问题的"
        return self._context.safe_get_entity_name(stage_entity)

    #######################################################################################################################################
    def _retrieve_stage_graph(self, actor_entity: Entity) -> List[str]:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        assert stage_entity is not None, "stage is None, actor无所在场景是有问题的"
        return stage_entity.get(StageGraphComponent).stage_graph.copy()

    #######################################################################################################################################
