from entitas import Entity, Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from gameplay_systems.components import (
    ActorComponent,
    PlanningAllowedComponent,
    StageGraphComponent,
    PlayerComponent,
)
from gameplay_systems.action_components import (
    StageNarrateAction,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
    PickUpPropAction,
    GoToAction,
    TagAction,
)
from my_agent.agent_plan import AgentPlanResponse
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, Set, List, Optional
import gameplay_systems.action_helper
import gameplay_systems.public_builtin_prompt as public_builtin_prompt
from my_agent.agent_task import (
    AgentTask,
)
from rpg_game.rpg_game import RPGGame
from gameplay_systems.check_self_helper import SelfChecker
from extended_systems.files_def import PropFile
from my_data.model_def import PropType


###############################################################################################################################################
def _generate_actor_props_prompts(
    props_dict: Dict[str, List[PropFile]],
    order_keys: List[str] = [
        PropType.TYPE_SPECIAL,
        PropType.TYPE_WEAPON,
        PropType.TYPE_CLOTHES,
        PropType.TYPE_NON_CONSUMABLE_ITEM,
        PropType.TYPE_SKILL,
    ],
) -> List[str]:

    ret: List[str] = []

    for key in order_keys:
        if key not in props_dict:
            continue

        for prop_file in props_dict[key]:
            ret.append(
                public_builtin_prompt.generate_prop_prompt(
                    prop_file,
                    description_prompt=True,
                    appearance_prompt=True,
                    attr_prompt=True,
                )
            )

    return ret


###############################################################################################################################################
def _generate_actor_plan_prompt(
    game_round: int,
    current_stage: str,
    stage_enviro_narrate: str,
    stage_graph: Set[str],
    props_in_stage: List[PropFile],
    info_of_actors_in_stage: Dict[str, str],
    health: float,
    actor_props: Dict[str, List[PropFile]],
    current_weapon: Optional[PropFile],
    current_clothes: Optional[PropFile],
) -> str:

    health *= 100

    actor_props_prompt = _generate_actor_props_prompts(actor_props)

    props_in_stage_prompt = [
        public_builtin_prompt.generate_prop_prompt(
            prop, description_prompt=False, appearance_prompt=True
        )
        for prop in props_in_stage
    ]

    actors_in_stage_prompt = "- 无任何角色。"
    if len(info_of_actors_in_stage) > 0:
        actors_in_stage_prompt = ""
        for actor_name, actor_appearance in info_of_actors_in_stage.items():
            actors_in_stage_prompt += (
                f"### {actor_name}\n- 角色外观:{actor_appearance}\n"
            )

    ret_prompt = f"""# {public_builtin_prompt.ConstantPrompt.ACTOR_PLAN_PROMPT_TAG} 请做出你的计划，决定你将要做什么

## 你当前所在的场景
{current_stage != "" and current_stage or "未知"}
### 场景描述
{stage_enviro_narrate != "" and stage_enviro_narrate or "无"}
### 从本场景可以去往的场景
{len(stage_graph) > 0 and "\n".join([f"- {stage}" for stage in stage_graph]) or "无可去往场景"}   

## 场景内的道具(可以进行交互，如: {PickUpPropAction.__name__})
{len(props_in_stage_prompt) > 0 and "\n".join(props_in_stage_prompt) or "- 无任何道具。"}

## 场景内的角色
{actors_in_stage_prompt}

## 你的健康状态
{f"生命值: {health:.2f}%"}

## 你当前持有的道具
{len(actor_props_prompt) > 0 and "\n".join(actor_props_prompt) or "- 无任何道具。"}

## 你当前装备的道具
- 武器: {current_weapon is not None and current_weapon.name or "无"}
- 衣服: {current_clothes is not None and current_clothes.name or "无"}

## 建议与注意事项
- 结合以上信息，决定你的下一步行动。
- 随时保持装备武器与衣服的状态(前提是你有对应的道具）。
- 注意！如果 从本场景可以去往的场景 为 无可去往场景，你就不可以执行{GoToAction.__name__}，因为系统的设计规则如此。

## 输出要求
- 请遵循 输出格式指南。
- 结果中要附带 {TagAction.__name__}。"""

    return ret_prompt


class ActorPlanningSystem(ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._tasks: Dict[str, AgentTask] = {}

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:
        # step1: 添加任务
        self._tasks.clear()
        self.fill_tasks(self._tasks)
        # step可选：混沌工程做测试
        self._context._chaos_engineering_system.on_actor_planning_system_execute(
            self._context
        )
        # step2: 并行执行requests
        if len(self._tasks) == 0:
            return

        responses = await AgentTask.gather([task for task in self._tasks.values()])
        if len(responses) == 0:
            logger.warning(f"ActorPlanningSystem: request_result is empty.")
            return

        self.handle(self._tasks)
        self._tasks.clear()

    #######################################################################################################################################
    def handle(self, request_tasks: Dict[str, AgentTask]) -> None:

        for name, task in request_tasks.items():

            if task is None:
                logger.warning(
                    f"ActorPlanningSystem: response is None or empty, so we can't get the planning."
                )
                continue

            entity = self._context.get_actor_entity(name)
            assert entity is not None, f"ActorPlanningSystem: entity is None, {name}"
            if entity is None:
                logger.warning(f"ActorPlanningSystem: entity is None, {name}")
                continue

            actor_comp = entity.get(ActorComponent)
            actor_planning = AgentPlanResponse(actor_comp.name, task.response_content)
            if not gameplay_systems.action_helper.validate_actions(
                actor_planning, ACTOR_AVAILABLE_ACTIONS_REGISTER
            ):
                logger.warning(
                    f"ActorPlanningSystem: check_plan failed, {actor_planning}"
                )
                ## 需要失忆!
                self._context._langserve_agent_system.remove_last_human_ai_conversation(
                    actor_comp.name
                )
                continue

            ## 不能停了，只能一直继续
            for action in actor_planning._actions:
                gameplay_systems.action_helper.add_action(
                    entity, action, ACTOR_AVAILABLE_ACTIONS_REGISTER
                )

    #######################################################################################################################################
    def fill_tasks(self, out_put_request_tasks: Dict[str, AgentTask]) -> None:

        out_put_request_tasks.clear()

        actor_entities = self._context.get_group(
            Matcher(
                all_of=[ActorComponent, PlanningAllowedComponent],
                none_of=[PlayerComponent],
            )
        ).entities
        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            agent = self._context._langserve_agent_system.get_agent(actor_comp.name)
            if agent is None:
                continue

            check_self = SelfChecker(self._context, actor_entity)
            actors_appearance = self._context.get_appearance_in_stage(actor_entity)
            actors_appearance.pop(actor_comp.name, None)  # 自己不要

            out_put_request_tasks[actor_comp.name] = AgentTask.create(
                agent,
                _generate_actor_plan_prompt(
                    game_round=self._game.round,
                    current_stage=self.get_stage_name(actor_entity),
                    stage_enviro_narrate=self.get_stage_narrate(actor_entity),
                    stage_graph=self.get_stage_graph(actor_entity),
                    props_in_stage=self.get_stage_props(actor_entity),
                    info_of_actors_in_stage=actors_appearance,
                    health=check_self.health,
                    actor_props=check_self._category_prop_files,
                    current_weapon=check_self._current_weapon,
                    current_clothes=check_self._current_clothes,
                ),
            )

    #######################################################################################################################################
    def get_stage_name(self, actor_entity: Entity) -> str:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        if stage_entity is None:
            logger.error("stage is None, actor无所在场景是有问题的")
            return ""

        return self._context.safe_get_entity_name(stage_entity)

    #######################################################################################################################################
    def get_stage_narrate(self, actor_entity: Entity) -> str:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        if stage_entity is None:
            logger.error("stage is None, actor无所在场景是有问题的")
            return ""

        if not stage_entity.has(StageNarrateAction):
            return ""

        stage_narrate_action = stage_entity.get(StageNarrateAction)
        return " ".join(stage_narrate_action.values)

    #######################################################################################################################################
    def get_stage_props(self, actor_entity: Entity) -> List[PropFile]:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        if stage_entity is None:
            logger.error("stage is None, actor无所在场景是有问题的")
            return []
        return self._context._file_system.get_files(
            PropFile, self._context.safe_get_entity_name(stage_entity)
        )

    #######################################################################################################################################
    def get_stage_graph(self, actor_entity: Entity) -> Set[str]:
        stage_entity = self._context.safe_get_stage_entity(actor_entity)
        if stage_entity is None:
            logger.error("stage is None, actor无所在场景是有问题的")
            return set()

        if not stage_entity.has(StageGraphComponent):
            return set()

        stage_graph: Set[str] = stage_entity.get(StageGraphComponent).stage_graph
        return stage_graph.copy()

    #######################################################################################################################################
