from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from gameplay_systems.action_components import (
    BehaviorAction,
    SkillTargetAction,
    SkillAction,
    SkillUsePropAction,
    TagAction,
    MindVoiceAction,
    WorldSkillSystemRuleAction,
)
from gameplay_systems.components import (
    BodyComponent,
    ActorComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, List, Set, Dict, Any, cast
from loguru import logger
from extended_systems.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from my_agent.agent_task import AgentTask, AgentTasksGather
from my_agent.agent_plan_and_action import AgentPlan
from rpg_game.rpg_game import RPGGame


class SelfSkillUsageCheckResponse(AgentPlan):

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def bool_tag(self) -> bool:
        tag_action = self.get_by_key(TagAction.__name__)
        if tag_action is None or len(tag_action.values) == 0:
            return False
        return (
            tag_action.values[0].lower() == "yes"
            or tag_action.values[0].lower() == "true"
        )

    @property
    def out_come(self) -> str:
        mind_voice_action = self.get_by_key(MindVoiceAction.__name__)
        if mind_voice_action is None or len(mind_voice_action.values) == 0:
            return ""
        return " ".join(mind_voice_action.values)


class SelfSkillUsageCheckSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)

        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._react_entities_copy: List[Entity] = []

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SkillAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(SkillAction)
            and entity.has(SkillTargetAction)
            and entity.has(BehaviorAction)
            and entity.has(ActorComponent)
        )

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        self._react_entities_copy = entities.copy()

    ######################################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        await self._execute(self._react_entities_copy)
        self._react_entities_copy.clear()

    ######################################################################################################################################################
    async def _execute(self, entities: List[Entity]) -> None:

        if len(entities) == 0:
            return

        tasks = self.create_tasks(entities)
        if len(tasks) == 0:
            self.on_remove_all(entities)
            return

        responses = await AgentTasksGather(
            "",
            [task for task in tasks.values()],
        ).gather()

        if len(responses) == 0:
            logger.debug(f"phase1_response is None.")
            self.on_remove_all(entities)
            return

        self.handle_tasks(tasks)

    ######################################################################################################################################################
    def handle_tasks(self, tasks: Dict[str, AgentTask]) -> None:

        for agent_name, task in tasks.items():

            actor_entity = self._context.get_actor_entity(agent_name)
            if actor_entity is None:
                continue

            if task.response_content == "":
                # 没有回答，直接清除所有的action
                self.on_remove_action(actor_entity)
                continue

            response_plan = SelfSkillUsageCheckResponse(
                agent_name, task.response_content
            )

            if not response_plan.bool_tag:
                # 失败就不用继续了，直接清除所有的action
                self.on_remove_action(actor_entity)

    ######################################################################################################################################################
    def on_remove_action(
        self,
        entity: Entity,
        action_comps: Set[type[Any]] = {
            BehaviorAction,
            SkillAction,
            SkillTargetAction,
            SkillUsePropAction,
            WorldSkillSystemRuleAction,
        },
    ) -> None:

        for action_comp in action_comps:
            if entity.has(action_comp):
                entity.remove(action_comp)

    ######################################################################################################################################################
    def on_remove_all(self, entities: List[Entity]) -> None:
        for entity in entities:
            self.on_remove_action(entity)

    ######################################################################################################################################################
    def extract_skill_files(self, entity: Entity) -> List[PropFile]:
        assert entity.has(SkillAction) and entity.has(SkillTargetAction)

        ret: List[PropFile] = []

        safe_name = self._context.safe_get_entity_name(entity)
        skill_action = entity.get(SkillAction)
        for skill_name in skill_action.values:

            skill_file = self._context._file_system.get_file(
                PropFile, safe_name, skill_name
            )
            if skill_file is None or not skill_file.is_skill:
                continue

            ret.append(skill_file)

        return ret

    ######################################################################################################################################################
    def extract_body_info(self, entity: Entity) -> str:
        if not entity.has(BodyComponent):
            return ""
        return str(entity.get(BodyComponent).body)

    ######################################################################################################################################################
    def extract_prop_files(self, entity: Entity) -> List[PropFile]:
        if not entity.has(SkillUsePropAction):
            return []

        safe_name = self._context.safe_get_entity_name(entity)
        prop_action = entity.get(SkillUsePropAction)
        ret: List[PropFile] = []
        for prop_name in prop_action.values:
            prop_file = self._context._file_system.get_file(
                PropFile, safe_name, prop_name
            )
            if prop_file is None:
                continue
            ret.append(prop_file)

        return ret

    ######################################################################################################################################################
    def create_tasks(self, entities: List[Entity]) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        for entity in entities:

            agent_name = self._context.safe_get_entity_name(entity)

            agent = self._context._langserve_agent_system.get_agent(agent_name)
            if agent is None:
                continue

            prompt = builtin_prompt.make_skill_usage_reasoning_prompt(
                agent_name,
                self.extract_body_info(entity),
                self.extract_skill_files(entity),
                self.extract_prop_files(entity),
            )

            # 会添加上下文的！！！！
            ret[agent._name] = AgentTask.create(
                agent,
                builtin_prompt.replace_you(prompt, agent_name),
            )

        return ret

    ######################################################################################################################################################
