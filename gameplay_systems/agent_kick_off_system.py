from entitas import Entity, Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from my_components.components import (
    WorldComponent,
    StageComponent,
    ActorComponent,
    AppearanceComponent,
    KickOffContentComponent,
    KickOffFlagComponent,
    AgentConnectionFlagComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, Set, FrozenSet, Any, List, final
from my_agent.agent_task import AgentTask
from rpg_game.rpg_game import RPGGame
from extended_systems.prop_file import PropFile, generate_prop_file_appearance_prompt
from my_components.action_components import (
    STAGE_AVAILABLE_ACTIONS_REGISTER,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
    MindVoiceAction,
    TagAction,
    StageNarrateAction,
    UpdateAppearanceAction,
)
import gameplay_systems.action_helper
from my_agent.agent_plan import AgentPlanResponse
from my_components.action_components import UpdateAppearanceAction


###############################################################################################################################################
def _generate_actor_kick_off_prompt(kick_off_message: str) -> str:

    ret_prompt = f"""# 游戏世界即将开始运行。这是你的初始设定，你将以此为起点进行游戏并更新你的状态

## 你的初始设定
{kick_off_message}

## 输出要求
- 请遵循 输出格式指南。
- 返回结果只带如下的键:{MindVoiceAction.__name__}与{TagAction.__name__}。"""

    return ret_prompt


###############################################################################################################################################
def _generate_stage_kick_off_prompt(
    kick_off_message: str,
    props_in_stage: List[PropFile],
    actors_in_stage: Set[str],
) -> str:

    props_prompt = "- 无任何道具。"
    if len(props_in_stage) > 0:
        props_prompt = ""
        for prop_file in props_in_stage:
            props_prompt += generate_prop_file_appearance_prompt(prop_file)

    actors_prompt = "- 无任何角色。"
    if len(actors_in_stage) > 0:
        actors_prompt = ""
        for actor_name in actors_in_stage:
            actors_prompt += f"- {actor_name}\n"

    ret_prompt = f"""# 游戏世界即将开始运行。这是你的初始设定，你将以此为起点进行游戏，并更新你的场景描述

## 场景内的道具
{props_prompt}

## 场景内的角色
{actors_prompt}

## 你的初始设定
{kick_off_message}

## {StageNarrateAction.__name__} 场景描述生成规则
- 不要对场景内角色未发生的对话，行为或心理活动进行任何猜测与推理。
- 注意！在输出内容中，移除所有与 场景内的角色 相关的描述。

## 输出要求
- 请遵循 输出格式指南。
- 返回结果只包含:{StageNarrateAction.__name__} 和 {TagAction.__name__}。"""
    return ret_prompt


###############################################################################################################################################
def _generate_world_system_kick_off_prompt() -> str:
    return f"""# 游戏世界即将开始运行。请回答你的职能与描述"""


######################################################################################################################################################
@final
class AgentKickOffSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ######################################################################################################################################################
    def _create_tasks(self) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        world_tasks = self._create_world_system_tasks()
        stage_tasks = self._create_stage_tasks()
        actor_tasks = self._create_actor_tasks()

        ret.update(world_tasks)
        ret.update(stage_tasks)
        ret.update(actor_tasks)

        return ret

    ######################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ######################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        tasks: Dict[str, AgentTask] = self._create_tasks()
        if len(tasks) == 0:
            return

        # 执行全部的任务
        await AgentTask.gather([task for task in tasks.values()])

        # 处理结果
        self._handle_responses(tasks)

        # 初始化更新外观的action
        self._initialize_appearance_update_action(tasks)

    ######################################################################################################################################################
    def _create_world_system_tasks(self) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        world_entities: Set[Entity] = self._context.get_group(
            Matcher(
                all_of=[
                    WorldComponent,
                    KickOffContentComponent,
                    AgentConnectionFlagComponent,
                ],
                none_of=[KickOffFlagComponent],
            )
        ).entities
        for world_entity in world_entities:

            world_comp = world_entity.get(WorldComponent)
            agent = self._context.agent_system.get_agent(world_comp.name)
            if agent is None:
                continue

            assert (
                len(agent._chat_history) == 0
            ), f"chat_history is not empty, {agent._chat_history}"

            ret[world_comp.name] = AgentTask.create(
                agent,
                _generate_world_system_kick_off_prompt(),
            )

        return ret

    ######################################################################################################################################################
    def _create_stage_tasks(self) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        stage_entities: Set[Entity] = self._context.get_group(
            Matcher(
                all_of=[
                    StageComponent,
                    KickOffContentComponent,
                    AgentConnectionFlagComponent,
                ],
                none_of=[KickOffFlagComponent],
            )
        ).entities
        for stage_entity in stage_entities:

            stage_comp = stage_entity.get(StageComponent)
            agent = self._context.agent_system.get_agent(stage_comp.name)
            if agent is None:
                continue

            assert (
                len(agent._chat_history) == 0
            ), f"chat_history is not empty, {agent._chat_history}"

            kick_off_comp = stage_entity.get(KickOffContentComponent)
            kick_off_prompt = _generate_stage_kick_off_prompt(
                kick_off_comp.content,
                self._context._file_system.get_files(
                    PropFile, self._context.safe_get_entity_name(stage_entity)
                ),
                self._context.get_actor_names_in_stage(stage_entity),
            )

            ret[stage_comp.name] = AgentTask.create(agent, kick_off_prompt)

        return ret

    ######################################################################################################################################################
    def _create_actor_tasks(self) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        actor_entities: Set[Entity] = self._context.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                    KickOffContentComponent,
                    AgentConnectionFlagComponent,
                ],
                none_of=[KickOffFlagComponent],
            )
        ).entities
        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            agent = self._context.agent_system.get_agent(actor_comp.name)
            if agent is None:
                continue

            assert (
                len(agent._chat_history) == 0
            ), f"chat_history is not empty, {agent._chat_history}"

            kick_off_comp = actor_entity.get(KickOffContentComponent)
            ret[actor_comp.name] = AgentTask.create(
                agent,
                _generate_actor_kick_off_prompt(
                    kick_off_comp.content,
                ),
            )

        return ret

    ######################################################################################################################################################
    def _handle_responses(self, tasks: Dict[str, AgentTask]) -> None:

        for agent_name, agent_task in tasks.items():

            entity = self._context.get_entity_by_name(agent_name)
            if entity is None:
                assert False, f"entity is None, {agent_name}"
                continue

            actions_register = self._resolve_actions_register(agent_name)
            if len(actions_register) == 0:

                assert entity.has(
                    WorldComponent
                ), f"entity has no world component, {agent_name}"

                self._add_kick_off_flag(entity, agent_name)
                continue

            assert entity.has(StageComponent) or entity.has(
                ActorComponent
            ), f"entity has no stage or actor component, {agent_name}"

            agent_planning = AgentPlanResponse(agent_name, agent_task.response_content)
            if not gameplay_systems.action_helper.validate_actions(
                agent_planning, actions_register
            ):
                logger.warning(
                    f"ActorPlanningSystem: check_plan failed, {agent_planning.original_response_content}"
                )

                self._context.agent_system.remove_last_human_ai_conversation(agent_name)
                continue

            for action in agent_planning._actions:
                gameplay_systems.action_helper.add_action(
                    entity, action, actions_register
                )

            self._add_kick_off_flag(entity, agent_name)

    ######################################################################################################################################################
    def _add_kick_off_flag(self, entity: Entity, agent_name: str) -> None:
        entity.replace(KickOffFlagComponent, agent_name)

    ######################################################################################################################################################
    def _resolve_actions_register(self, name: str) -> FrozenSet[type[Any]]:

        entity = self._context.get_entity_by_name(name)
        if entity is None:
            return frozenset()

        if entity.has(ActorComponent):
            return ACTOR_AVAILABLE_ACTIONS_REGISTER
        elif entity.has(StageComponent):
            return STAGE_AVAILABLE_ACTIONS_REGISTER
        else:
            assert entity.has(WorldComponent), f"entity has no world component, {name}"

        return frozenset()

    ######################################################################################################################################################
    def _initialize_appearance_update_action(self, tasks: Dict[str, AgentTask]) -> None:

        actor_entities = self._context.get_group(
            Matcher(
                all_of=[
                    AppearanceComponent,
                    KickOffFlagComponent,
                ]
            )
        ).entities

        for actor_entity in actor_entities:

            safe_name = self._context.safe_get_entity_name(actor_entity)
            if safe_name not in tasks:
                continue

            actor_entity.replace(
                UpdateAppearanceAction,
                self._context.safe_get_entity_name(actor_entity),
                [],
            )

    ######################################################################################################################################################
