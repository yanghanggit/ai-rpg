from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from ecs_systems.action_components import (
    BehaviorAction,
    TargetAction,
    SkillAction,
    PropAction,
    TagAction,
    BroadcastAction,
)
from ecs_systems.components import (
    AppearanceComponent,
    RPGCurrentWeaponComponent,
    RPGCurrentClothesComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, Any, List, cast, Optional, Set
from loguru import logger
from file_system.files_def import PropFile
import ecs_systems.cn_builtin_prompt as builtin_prompt
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask
from my_agent.agent_plan import AgentPlan
from ecs_systems.cn_constant_prompt import _CNConstantPrompt_
import gameplay.planning_helper
from ecs_systems.action_components import (
    STAGE_AVAILABLE_ACTIONS_REGISTER,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
)
from ecs_systems.stage_director_event import IStageDirectorEvent
import ecs_systems.cn_builtin_prompt as builtin_prompt
from ecs_systems.stage_director_component import StageDirectorComponent
from ecs_systems.behavior_action_system import WorldBehaviorCheckEvent


class NotifyReleaseSkillEvent(IStageDirectorEvent):

    def __init__(self, actor_name: str, behavior_sentece: str) -> None:

        self._actor_name: str = actor_name
        self._behavior_sentece: str = behavior_sentece

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        return builtin_prompt.make_notify_skill_event_prompt(
            self._actor_name, self._behavior_sentece
        )

    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return builtin_prompt.make_notify_skill_event_prompt(
            self._actor_name, self._behavior_sentece
        )


class WorldSkillSystemResponsePlan(AgentPlan):

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def result(self) -> str:
        tip_action = self.get_by_key(TagAction.__name__)
        if tip_action is None or len(tip_action.values) == 0:
            return _CNConstantPrompt_.FAILURE
        return tip_action.values[0]

    @property
    def behavior_sentence(self) -> str:
        broadcast_action = self.get_by_key(BroadcastAction.__name__)
        if broadcast_action is None or len(broadcast_action.values) == 0:
            return ""
        return " ".join(broadcast_action.values)


class SkillActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, world_system_name: str) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._world_system_name: str = world_system_name

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SkillAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(SkillAction)
            and entity.has(TargetAction)
            and entity.has(BehaviorAction)
        )

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ######################################################################################################################################################
    def handle(self, entity: Entity) -> None:

        assert entity.has(SkillAction) and entity.has(TargetAction)

        world_entity = self._context.get_world_entity(self._world_system_name)
        if world_entity is None:
            logger.warning(f"{self._world_system_name}, world_entity is None.")
            return

        appearance = self.get_appearance(entity)

        skill_files = self.get_skill_files(entity)

        prop_files = self.get_prop_files(entity)
        prop_files.extend(self.get_current_using_prop(entity))

        world_response_plan = self.request_world_skill_system_check(
            entity, world_entity, appearance, skill_files, prop_files
        )

        if world_response_plan is None:
            logger.debug(
                f"{self._world_system_name}, determine_skill_enable_ret is None."
            )

            self.on_stage_director_world_behavior_check_event(
                entity, self.get_behavior_sentence(entity), False
            )
            return

        if (
            world_response_plan.result == _CNConstantPrompt_.BIG_FAILURE
            or world_response_plan.result == _CNConstantPrompt_.FAILURE
        ):
            logger.debug(
                f"{self._world_system_name}, determine_skill_enable_ret is BIG_FAILURE."
            )
            self.on_stage_director_world_behavior_check_event(
                entity, self.get_behavior_sentence(entity), False
            )
            return

        for target in self.get_targets(entity):

            self.on_stage_director_notify_release_skill_event(
                entity, world_response_plan.behavior_sentence
            )

            skill_reponse_plan = self.request_release_skill(
                entity,
                target,
                appearance,
                skill_files,
                prop_files,
                world_response_plan,
                self.get_behavior_sentence(entity),
            )

            if skill_reponse_plan is None:
                logger.debug(f"{self._world_system_name}, response_plan is None.")
                continue

            self.add_actions(target, skill_reponse_plan)

    ######################################################################################################################################################

    def get_behavior_sentence(self, entity: Entity) -> str:
        behavior_action = entity.get(BehaviorAction)
        if behavior_action is None or len(behavior_action.values) == 0:
            return ""
        return cast(str, behavior_action.values[0])

    ######################################################################################################################################################
    def get_targets(self, entity: Entity) -> Set[Entity]:
        assert entity.has(TargetAction)
        targets = set()
        for target_name in entity.get(TargetAction).values:
            target = self._context.get_entity_by_name(target_name)
            if target is not None:
                targets.add(target)
        return targets

    ######################################################################################################################################################
    def request_release_skill(
        self,
        entity: Entity,
        target: Entity,
        appearance: str,
        skill_files: List[PropFile],
        prop_files: List[PropFile],
        world_response_plan: WorldSkillSystemResponsePlan,
        behavior_sentence: str,
    ) -> Optional[AgentPlan]:

        agent_name = self._context.safe_get_entity_name(target)
        agent = self._context._langserve_agent_system.get_agent(agent_name)
        if agent is None:
            return None

        prompt = builtin_prompt.make_reasoning_skill_target_feedback_prompt(
            self._context.safe_get_entity_name(entity),
            agent_name,
            appearance,
            skill_files,
            prop_files,
            world_response_plan.behavior_sentence,
            world_response_plan.result,
            behavior_sentence,
        )

        logger.debug(prompt)
        task = LangServeAgentRequestTask.create(
            agent,
            builtin_prompt.replace_mentions_of_your_name_with_you_prompt(
                prompt, agent_name
            ),
        )

        if task is None:
            return None

        response = task.request()
        if response is None:
            logger.debug(f"{agent._name}, response is None.")
            return None

        return AgentPlan(agent._name, response)

    ######################################################################################################################################################
    def add_actions(self, target: Entity, agent_plan: AgentPlan) -> None:

        all_register: List[Any] = (
            STAGE_AVAILABLE_ACTIONS_REGISTER + ACTOR_AVAILABLE_ACTIONS_REGISTER
        )

        if not gameplay.planning_helper.check_plan(target, agent_plan, all_register):
            logger.warning(f"ActorPlanningSystem: check_plan failed, {agent_plan}")
            ## 需要失忆!
            self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(
                agent_plan._name
            )
            return

        ## 不能停了，只能一直继续
        for action in agent_plan._actions:
            gameplay.planning_helper.add_action_component(target, action, all_register)

    ######################################################################################################################################################
    def request_world_skill_system_check(
        self,
        entity: Entity,
        world_entity: Entity,
        appearance: str,
        skill_files: List[PropFile],
        prop_files: List[PropFile],
    ) -> Optional[WorldSkillSystemResponsePlan]:

        # 生成提示
        prompt = builtin_prompt.make_world_reasoning_release_skill_enable_prompt(
            self._context.safe_get_entity_name(entity),
            appearance,
            skill_files,
            prop_files,
        )

        agent = self._context._langserve_agent_system.get_agent(
            self._context.safe_get_entity_name(world_entity)
        )
        if agent is None:
            return None

        task = LangServeAgentRequestTask.create_without_context(agent, prompt)
        if task is None:
            return None

        response = task.request()
        if response is None:
            logger.debug(f"{self._world_system_name}, response is None.")
            return None

        return WorldSkillSystemResponsePlan(agent._name, response)

    ######################################################################################################################################################
    def get_skill_files(self, entity: Entity) -> List[PropFile]:
        assert entity.has(SkillAction) and entity.has(TargetAction)

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
    def get_appearance(self, entity: Entity) -> str:
        assert entity.has(AppearanceComponent)
        if not entity.has(AppearanceComponent):
            return ""
        return str(entity.get(AppearanceComponent).appearance)

    ######################################################################################################################################################
    def get_prop_files(self, entity: Entity) -> List[PropFile]:
        if not entity.has(PropAction):
            return []

        safe_name = self._context.safe_get_entity_name(entity)
        prop_action = entity.get(PropAction)
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
    def get_current_using_prop(self, entity: Entity) -> List[PropFile]:

        ret: List[PropFile] = []

        if entity.has(RPGCurrentWeaponComponent):
            current_weapon_comp = entity.get(RPGCurrentWeaponComponent)
            weapon_file = self._context._file_system.get_file(
                PropFile,
                cast(str, current_weapon_comp.name),
                cast(str, current_weapon_comp.propname),
            )
            if weapon_file is not None:
                ret.append(weapon_file)

        if entity.has(RPGCurrentClothesComponent):
            current_clothes_comp = entity.get(RPGCurrentClothesComponent)
            clothes_file = self._context._file_system.get_file(
                PropFile,
                cast(str, current_clothes_comp.name),
                cast(str, current_clothes_comp.propname),
            )
            if clothes_file is not None:
                ret.append(clothes_file)

        return ret

    ######################################################################################################################################################
    def on_stage_director_world_behavior_check_event(
        self, entity: Entity, behavior_sentence: str, allow: bool
    ) -> None:
        # 导演类来统筹
        StageDirectorComponent.add_event_to_stage_director(
            self._context,
            entity,
            WorldBehaviorCheckEvent(
                self._context.safe_get_entity_name(entity), behavior_sentence, allow
            ),
        )

    ######################################################################################################################################################
    def on_stage_director_notify_release_skill_event(
        self, entity: Entity, behavior_sentece: str
    ) -> None:

        # 导演类来统筹
        StageDirectorComponent.add_event_to_stage_director(
            self._context,
            entity,
            NotifyReleaseSkillEvent(
                self._context.safe_get_entity_name(entity), behavior_sentece
            ),
        )

    ######################################################################################################################################################
