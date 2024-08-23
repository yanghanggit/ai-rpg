from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from ecs_systems.action_components import (
    BehaviorAction,
    TargetAction,
    SkillAction,
    PropAction,
)
from ecs_systems.components import StageComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, Set
from file_system.files_def import PropFile

# from ecs_systems.stage_director_event import IStageDirectorEvent
import ecs_systems.cn_builtin_prompt as builtin_prompt

# from ecs_systems.stage_director_component import StageDirectorComponent


# class WorldBehaviorCheckEvent(IStageDirectorEvent):

#     def __init__(self, actor_name: str, behavior_sentece: str, allow: bool) -> None:

#         self._actor_name: str = actor_name
#         self._behavior_sentece: str = behavior_sentece
#         self._allow: bool = allow

#     def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
#         if actor_name != self._actor_name:
#             # 只有自己知道
#             return ""

#         return builtin_prompt.make_world_reasoning_behavior_check_prompt(
#             self._actor_name, self._behavior_sentece, self._allow
#         )

#     def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
#         return ""


class BehaviorActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(BehaviorAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(BehaviorAction)

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ######################################################################################################################################################
    def handle(self, entity: Entity) -> None:

        behavior_action: BehaviorAction = entity.get(BehaviorAction)
        if len(behavior_action.values) == 0:
            return

        behavior_sentence = behavior_action.values[0]
        if behavior_sentence == "":
            return

        targets = self.parse_targets(entity, behavior_sentence)
        skills = self.parse_skills(entity, behavior_sentence)
        props = self.parse_props(entity, behavior_sentence)
        if len(targets) == 0 or len(skills) == 0:
            self.on_stage_director_world_behavior_check_event(
                entity, behavior_sentence, False
            )
            return

        self.clear_action(entity)
        self.add_target_action(entity, targets)
        self.add_skill_action(entity, skills)
        self.add_prop_action(entity, props)

        # 导演类来统筹
        self.on_stage_director_world_behavior_check_event(
            entity, behavior_sentence, True
        )

    ######################################################################################################################################################
    def clear_action(self, entity: Entity) -> None:

        if entity.has(TargetAction):
            entity.remove(TargetAction)

        if entity.has(SkillAction):
            entity.remove(SkillAction)

        if entity.has(PropAction):
            entity.remove(PropAction)

    ######################################################################################################################################################
    def parse_targets(self, entity: Entity, sentence: str) -> Set[str]:

        current_stage_entity = self._context.safe_get_stage_entity(entity)
        assert current_stage_entity is not None
        if current_stage_entity is None:
            return set()

        current_stage_name = current_stage_entity.get(StageComponent).name
        if current_stage_name in sentence:
            # 有场景就是直接是场景的。放弃下面的处理！
            return set({current_stage_name})

        ret: Set[str] = set()
        actor_names = self._context.get_actor_names_in_stage(current_stage_entity)
        for actor_name in actor_names:
            if actor_name in sentence:
                ret.add(actor_name)
        return ret

    ######################################################################################################################################################
    def add_target_action(self, entity: Entity, targets: Set[str]) -> None:
        if len(targets) == 0:
            return
        safe_name = self._context.safe_get_entity_name(entity)
        entity.add(TargetAction, safe_name, TargetAction.__name__, list(targets))

    ######################################################################################################################################################
    def parse_skills(self, entity: Entity, sentence: str) -> Set[PropFile]:

        safe_name = self._context.safe_get_entity_name(entity)
        skill_files = self._context._file_system.get_files(PropFile, safe_name)

        ret: Set[PropFile] = set()
        for skill_file in skill_files:
            if not skill_file.is_skill:
                continue

            if skill_file.name in sentence:
                ret.add(skill_file)

        return ret

    ######################################################################################################################################################
    def add_skill_action(self, entity: Entity, skills: Set[PropFile]) -> None:
        if len(skills) == 0:
            return
        safe_name = self._context.safe_get_entity_name(entity)
        skill_names = [skill.name for skill in skills]
        entity.add(SkillAction, safe_name, SkillAction.__name__, skill_names)

    ######################################################################################################################################################
    def parse_props(self, entity: Entity, sentence: str) -> Set[PropFile]:

        safe_name = self._context.safe_get_entity_name(entity)
        prop_files = self._context._file_system.get_files(PropFile, safe_name)
        ret: Set[PropFile] = set()
        for prop_file in prop_files:
            if prop_file.is_skill:
                continue
            if prop_file.name in sentence:
                ret.add(prop_file)

        return ret

    ######################################################################################################################################################
    def add_prop_action(self, entity: Entity, props: Set[PropFile]) -> None:
        if len(props) == 0:
            return
        safe_name = self._context.safe_get_entity_name(entity)
        prop_names = [prop.name for prop in props]
        entity.add(PropAction, safe_name, PropAction.__name__, prop_names)

    ######################################################################################################################################################
    def on_stage_director_world_behavior_check_event(
        self, entity: Entity, behavior_sentence: str, allow: bool
    ) -> None:
        # StageDirectorComponent.add_event_to_stage_director(
        #     self._context,
        #     entity,
        #     WorldBehaviorCheckEvent(
        #         self._context.safe_get_entity_name(entity), behavior_sentence, allow
        #     ),
        # )

        message = builtin_prompt.make_world_reasoning_behavior_check_prompt(
            self._context.safe_get_entity_name(entity), behavior_sentence, allow
        )
        # 只有自己
        self._context.add_agent_context_message(set({entity}), message)

    ######################################################################################################################################################
