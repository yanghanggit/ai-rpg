from entitas import Entity, Matcher, InitializeProcessor, ExecuteProcessor  # type: ignore
from overrides import override
from gameplay_systems.components import (
    WorldComponent,
    StageComponent,
    ActorComponent,
    AppearanceComponent,
    BodyComponent,
)
import gameplay_systems.public_builtin_prompt as public_builtin_prompt
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import Dict, Set, FrozenSet, Any, List
from my_agent.agent_task import AgentTask
from rpg_game.rpg_game import RPGGame
from extended_systems.files_def import PropFile
from gameplay_systems.action_components import (
    STAGE_AVAILABLE_ACTIONS_REGISTER,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
    MindVoiceAction,
    TagAction,
    StageNarrateAction,
)
import gameplay_systems.action_helper
from my_agent.agent_plan import AgentPlanResponse
from gameplay_systems.action_components import UpdateAppearanceAction


###############################################################################################################################################
def _generate_actor_kick_off_prompt(
    kick_off_message: str, about_game: str, game_round: int
) -> str:

    ret_prompt = f"""# {public_builtin_prompt.ConstantPrompt.ACTOR_KICK_OFF_MESSAGE_PROMPT_TAG} 游戏世界即将开始运行。这是你的初始设定，你将以此为起点进行游戏并更新你的状态

## 游戏背景与风格设定
{about_game}

## 你的初始设定
{kick_off_message}

## 输出要求
- 请遵循 输出格式指南。
- 返回结果只带如下的键:{MindVoiceAction.__name__}与{TagAction.__name__}。"""

    return ret_prompt


###############################################################################################################################################
def _generate_stage_kick_off_prompt(
    kick_off_message: str,
    about_game: str,
    props_in_stage: List[PropFile],
    actors_in_stage: Set[str],
    game_round: int,
) -> str:

    props_prompt = "- 无任何道具。"
    if len(props_in_stage) > 0:
        props_prompt = ""
        for prop_file in props_in_stage:
            props_prompt += public_builtin_prompt.generate_prop_prompt(
                prop_file, description_prompt=False, appearance_prompt=True
            )

    actors_prompt = "- 无任何角色。"
    if len(actors_in_stage) > 0:
        actors_prompt = ""
        for actor_name in actors_in_stage:
            actors_prompt += f"- {actor_name}\n"

    ret_prompt = f"""# {public_builtin_prompt.ConstantPrompt.STAGE_KICK_OFF_MESSAGE_PROMPT_TAG} 游戏世界即将开始运行。这是你的初始设定，你将以此为起点进行游戏，并更新你的场景描述

## 游戏背景与风格设定
{about_game}

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
def _generate_world_system_kick_off_prompt(about_game: str, game_round: int) -> str:
    return f"""# {public_builtin_prompt.ConstantPrompt.WORLD_SYSTEM_KICK_OFF_MESSAGE_PROMPT_TAG} 游戏世界即将开始运行。这是你的初始设定，请简要回答你的职能与描述
## 游戏背景与风格设定
{about_game}"""


######################################################################################################################################################
class AgentKickOffSystem(InitializeProcessor, ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

        self._tasks: Dict[str, AgentTask] = {}
        self._world_tasks: Dict[str, AgentTask] = {}
        self._stage_tasks: Dict[str, AgentTask] = {}
        self._actor_tasks: Dict[str, AgentTask] = {}

    ######################################################################################################################################################
    def clear_tasks(self) -> None:
        self._tasks.clear()
        self._world_tasks.clear()
        self._stage_tasks.clear()
        self._actor_tasks.clear()

    ######################################################################################################################################################
    @override
    def initialize(self) -> None:
        # 清除
        self.clear_tasks()
        # 生成任务
        self._world_tasks = self.create_world_system_tasks()
        self._stage_tasks = self.create_stage_tasks()
        self._actor_tasks = self.create_actor_tasks()

        # 填进去
        self._tasks.update(self._world_tasks)
        self._tasks.update(self._stage_tasks)
        self._tasks.update(self._actor_tasks)

    ######################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ######################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        if len(self._tasks) == 0:
            return

        responses = await AgentTask.gather([task for task in self._tasks.values()])
        if len(responses) == 0:
            return

        self.on_response(self._tasks)
        self.clear_tasks()  # 这句必须得走.
        self.on_add_update_appearance_action()

    ######################################################################################################################################################
    def create_world_system_tasks(self) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        world_entities: Set[Entity] = self._context.get_group(
            Matcher(WorldComponent)
        ).entities
        for world_entity in world_entities:

            world_comp = world_entity.get(WorldComponent)
            agent = self._context._langserve_agent_system.get_agent(world_comp.name)
            if agent is None:
                continue

            ret[world_comp.name] = AgentTask.create(
                agent,
                _generate_world_system_kick_off_prompt(
                    self._game.about_game, self._game.round
                ),
            )

        return ret

    ######################################################################################################################################################
    def create_stage_tasks(self) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        stage_entities: Set[Entity] = self._context.get_group(
            Matcher(StageComponent)
        ).entities
        for stage_entity in stage_entities:

            stage_comp = stage_entity.get(StageComponent)
            agent = self._context._langserve_agent_system.get_agent(stage_comp.name)
            if agent is None:
                continue

            kick_off_messages = self._context._kick_off_message_system.get_message(
                stage_comp.name
            )
            if len(kick_off_messages) == 0 or len(kick_off_messages) > 1:
                logger.error(f"kick_off_messages is error: {stage_comp.name}")
                continue

            kick_off_prompt = _generate_stage_kick_off_prompt(
                kick_off_messages[0].content,
                self._game.about_game,
                self._context._file_system.get_files(
                    PropFile, self._context.safe_get_entity_name(stage_entity)
                ),
                self._context.get_actor_names_in_stage(stage_entity),
                self._game.round,
            )

            ret[stage_comp.name] = AgentTask.create(agent, kick_off_prompt)

        return ret

    ######################################################################################################################################################
    def create_actor_tasks(self) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        actor_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities
        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            agent = self._context._langserve_agent_system.get_agent(actor_comp.name)
            if agent is None:
                continue

            kick_off_messages = self._context._kick_off_message_system.get_message(
                actor_comp.name
            )
            if len(kick_off_messages) == 0 or len(kick_off_messages) > 1:
                logger.error(f"kick_off_messages is error: {actor_comp.name}")
                continue

            ret[actor_comp.name] = AgentTask.create(
                agent,
                _generate_actor_kick_off_prompt(
                    kick_off_messages[0].content,
                    self._game.about_game,
                    self._game.round,
                ),
            )

        return ret

    ######################################################################################################################################################
    def on_response(self, tasks: Dict[str, AgentTask]) -> None:

        for name, task in tasks.items():

            if task is None:
                logger.warning(
                    f"ActorPlanningSystem: response is None or empty, so we can't get the planning."
                )
                continue

            if name in self._world_tasks:
                continue

            agent_planning = AgentPlanResponse(name, task.response_content)
            entity = self._context.get_actor_entity(
                name
            ) or self._context.get_stage_entity(name)
            if entity is None:
                logger.warning(f"ActorPlanningSystem: entity is None, {name}")
                continue

            if not gameplay_systems.action_helper.validate_actions(
                agent_planning, self.get_actions_register(name)
            ):
                logger.warning(
                    f"ActorPlanningSystem: check_plan failed, {agent_planning}"
                )
                ## 需要失忆!
                self._context._langserve_agent_system.remove_last_human_ai_conversation(
                    name
                )
                continue

            ## 不能停了，只能一直继续
            for action in agent_planning._actions:
                gameplay_systems.action_helper.add_action(
                    entity, action, self.get_actions_register(name)
                )

    ######################################################################################################################################################
    def get_actions_register(self, name: str) -> FrozenSet[type[Any]]:
        if name in self._stage_tasks:
            return STAGE_AVAILABLE_ACTIONS_REGISTER
        elif name in self._actor_tasks:
            return ACTOR_AVAILABLE_ACTIONS_REGISTER
        return frozenset()

    ######################################################################################################################################################
    def on_add_update_appearance_action(self) -> None:

        ## 第一次强制更新外观
        actor_entities = self._context.get_group(
            Matcher(all_of=[ActorComponent, AppearanceComponent, BodyComponent])
        ).entities

        for actor_entity in actor_entities:
            if not actor_entity.has(UpdateAppearanceAction):
                actor_entity.add(
                    UpdateAppearanceAction,
                    self._context.safe_get_entity_name(actor_entity),
                    [],
                )

    ######################################################################################################################################################
