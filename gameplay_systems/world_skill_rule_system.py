from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from gameplay_systems.action_components import (
    BehaviorAction,
    SkillTargetAction,
    SkillAction,
    SkillUsePropAction,
    TagAction,
    BroadcastAction,
    WorldSkillSystemRuleAction,
)
from gameplay_systems.components import (
    BodyComponent,
    ActorComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, List, cast, Set, Dict, Any
from loguru import logger
from extended_systems.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from my_agent.agent_task import AgentTask, AgentTasksGather
from my_agent.agent_plan_and_action import AgentPlan
from gameplay_systems.cn_constant_prompt import _CNConstantPrompt_ as ConstantPrompt
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from rpg_game.rpg_game import RPGGame
import extended_systems.file_system_helper


class WorldSkillRuleResponse(AgentPlan):

    OPTION_PARAM_NAME: str = "actor_name"

    def __init__(self, name: str, input_str: str, task: AgentTask) -> None:
        super().__init__(name, input_str)
        self._task: AgentTask = task

    @property
    def result_tag(self) -> str:
        tip_action = self.get_by_key(TagAction.__name__)
        if tip_action is None or len(tip_action.values) == 0:
            return ConstantPrompt.FAILURE
        return tip_action.values[0]

    @property
    def out_come(self) -> str:
        broadcast_action = self.get_by_key(BroadcastAction.__name__)
        if broadcast_action is None or len(broadcast_action.values) == 0:
            return ""
        return " ".join(broadcast_action.values)


######################################################################################################################################################


class WorldSkillRuleSystem(ReactiveProcessor):

    def __init__(
        self, context: RPGEntitasContext, rpg_game: RPGGame, system_name: str
    ) -> None:
        super().__init__(context)

        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._system_name: str = system_name
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

        if (
            self._context.get_world_entity(self._system_name) is not None
            and len(self._react_entities_copy) > 0
        ):
            await self._execute(self._react_entities_copy, self._system_name)

        self._react_entities_copy.clear()

    ######################################################################################################################################################
    async def _execute(
        self, entities: List[Entity], world_skill_system_name: str
    ) -> None:

        if len(entities) == 0:
            return

        # 第二个大阶段，全局技能系统检查技能组合是否合法
        tasks = self.create_tasks(entities, world_skill_system_name)
        if len(tasks) == 0:
            self.on_remove_all_actions(entities)
            return

        response = await AgentTasksGather("", tasks).gather()
        if len(response) == 0:
            self.on_remove_all_actions(entities)
            return

        response_plans = self.create_responses(tasks)
        self.handle_responses(response_plans)

    ######################################################################################################################################################
    def handle_responses(
        self, response_plans: Dict[str, WorldSkillRuleResponse]
    ) -> None:

        for actor_name, response_plan in response_plans.items():
            actor_entity = self._context.get_actor_entity(actor_name)
            if actor_entity is None:
                continue

            if response_plan._task.response_content == "":
                self.on_world_skill_system_off_line_event(actor_entity)
                continue

            match (response_plan.result_tag):
                case ConstantPrompt.FAILURE:
                    self.on_world_skill_system_rule_fail_event(
                        actor_entity, response_plan
                    )
                    self.on_remove_actions(actor_entity)
                case ConstantPrompt.SUCCESS:
                    self.on_world_skill_system_rule_success_event(
                        actor_entity, response_plan
                    )
                    self.add_world_skill_system_rule_success_action(
                        actor_entity, response_plan
                    )
                    self.consume_consumable_props(actor_entity)

                case ConstantPrompt.CRITICAL_SUCCESS:
                    self.on_world_skill_system_rule_success_event(
                        actor_entity, response_plan
                    )
                    self.add_world_skill_system_rule_success_action(
                        actor_entity, response_plan
                    )
                    self.consume_consumable_props(actor_entity)

                case _:
                    logger.error(f"Unknown tag: {response_plan.result_tag}")

    ######################################################################################################################################################
    def consume_consumable_props(self, entity: Entity) -> None:
        prop_files = self.extract_prop_files(entity)
        for prop_file in prop_files:
            if prop_file.is_consumable_item:
                extended_systems.file_system_helper.consume_consumable(
                    self._context._file_system, prop_file
                )

    ######################################################################################################################################################
    def add_world_skill_system_rule_success_action(
        self, entity: Entity, response_plan: WorldSkillRuleResponse
    ) -> None:

        actor_name = self._context.safe_get_entity_name(entity)
        entity.replace(
            WorldSkillSystemRuleAction,
            actor_name,
            WorldSkillSystemRuleAction.__name__,
            [response_plan.result_tag, response_plan.out_come],
        )

    ######################################################################################################################################################
    def create_responses(
        self, tasks: List[AgentTask]
    ) -> Dict[str, WorldSkillRuleResponse]:

        ret: Dict[str, WorldSkillRuleResponse] = {}

        for task in tasks:

            actor_name = task._option_param.get(
                WorldSkillRuleResponse.OPTION_PARAM_NAME, ""
            )
            entity = self._context.get_actor_entity(actor_name)
            if entity is None:
                continue

            response_plan = WorldSkillRuleResponse(
                task.agent_name, task.response_content, task
            )

            ret[actor_name] = response_plan

        return ret

    ######################################################################################################################################################
    def on_remove_actions(
        self,
        entity: Entity,
        action_comps: Set[type[Any]] = {
            BehaviorAction,
            SkillAction,
            SkillTargetAction,
            SkillUsePropAction,
        },
    ) -> None:

        for action_comp in action_comps:
            if entity.has(action_comp):
                entity.remove(action_comp)

    ######################################################################################################################################################
    def on_remove_all_actions(self, entities: List[Entity]) -> None:
        for entity in entities:
            self.on_remove_actions(entity)

    ######################################################################################################################################################

    def extract_behavior_sentence(self, entity: Entity) -> str:
        behavior_action = entity.get(BehaviorAction)
        if behavior_action is None or len(behavior_action.values) == 0:
            return ""
        return cast(str, behavior_action.values[0])

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
    def on_world_skill_system_off_line_event(self, entity: Entity) -> None:
        self._context.broadcast_entities(
            set({entity}),
            builtin_prompt.make_world_skill_system_off_line_prompt(
                self._context.safe_get_entity_name(entity),
                self.extract_behavior_sentence(entity),
            ),
        )

    ######################################################################################################################################################
    def on_world_skill_system_rule_success_event(
        self, entity: Entity, world_response_plan: WorldSkillRuleResponse
    ) -> None:

        target_entities = self.extract_targets(entity)
        target_names: Set[str] = set()
        for target_entity in target_entities:
            target_names.add(self._context.safe_get_entity_name(target_entity))

        self._context.broadcast_entities(
            set({entity}),
            builtin_prompt.make_world_skill_system_rule_success_prompt(
                self._context.safe_get_entity_name(entity),
                target_names,
                world_response_plan.result_tag,
                self.extract_behavior_sentence(entity),
                world_response_plan.out_come,
            ),
        )

    ######################################################################################################################################################
    def on_world_skill_system_rule_fail_event(
        self, entity: Entity, world_response_plan: WorldSkillRuleResponse
    ) -> None:
        self._context.broadcast_entities(
            set({entity}),
            builtin_prompt.make_world_skill_system_rule_fail_prompt(
                self._context.safe_get_entity_name(entity),
                world_response_plan.result_tag,
                self.extract_behavior_sentence(entity),
                world_response_plan.out_come,
            ),
        )

    ######################################################################################################################################################
    def create_tasks(
        self, entities: List[Entity], world_skill_system_name: str
    ) -> List[AgentTask]:

        ret: List[AgentTask] = []

        world_system_agent = self._context._langserve_agent_system.get_agent(
            world_skill_system_name
        )
        if world_system_agent is None:
            return ret

        for entity in entities:

            prompt = builtin_prompt.make_world_skill_system_rule_prompt(
                self._context.safe_get_entity_name(entity),
                self.extract_body_info(entity),
                self.extract_skill_files(entity),
                self.extract_prop_files(entity),
                self.extract_behavior_sentence(entity),
            )

            task = AgentTask.create_process_context_without_saving(
                world_system_agent, prompt
            )
            if task is None:
                continue

            safe_name = self._context.safe_get_entity_name(entity)
            task._option_param.setdefault(
                WorldSkillRuleResponse.OPTION_PARAM_NAME, safe_name
            )
            ret.append(task)

        return ret

    ######################################################################################################################################################
    def extract_targets(self, entity: Entity) -> Set[Entity]:
        assert entity.has(SkillTargetAction)
        targets = set()
        for target_name in entity.get(SkillTargetAction).values:
            target = self._context.get_entity_by_name(target_name)
            if target is not None:
                targets.add(target)
        return targets

    ######################################################################################################################################################
