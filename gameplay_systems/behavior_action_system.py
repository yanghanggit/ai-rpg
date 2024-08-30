from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from gameplay_systems.action_components import (
    BehaviorAction,
    SkillTargetAction,
    SkillAction,
    SkillPropAction,
)
from gameplay_systems.components import StageComponent, RPGCurrentWeaponComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, Set, Optional
from file_system.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from rpg_game.rpg_game import RPGGame


class BehaviorActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

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

        # 基础数据
        targets = self.parse_targets(entity, behavior_sentence)
        skills = self.parse_skills(entity, behavior_sentence)
        props = self.parse_props(entity, behavior_sentence)

        # 默认会添加当前武器
        weapon_prop = self.get_current_weapon(entity)
        if weapon_prop is not None:
            props.add(weapon_prop)

        # 不用继续了
        if len(targets) == 0 or len(skills) == 0:
            self.on_behavior_check_event(entity, behavior_sentence, False)
            return

        # 添加动作
        self.clear_action(entity)
        self.add_target_action(entity, targets)
        self.add_skill_action(entity, skills)
        self.add_prop_action(entity, props)

        # 事件通知
        self.on_behavior_check_event(entity, behavior_sentence, True)

    ######################################################################################################################################################
    def get_current_weapon(self, entity: Entity) -> Optional[PropFile]:
        if not entity.has(RPGCurrentWeaponComponent):
            return None
        current_weapon_comp = entity.get(RPGCurrentWeaponComponent)
        return self._context._file_system.get_file(
            PropFile, current_weapon_comp.name, current_weapon_comp.propname
        )

    ######################################################################################################################################################
    def clear_action(self, entity: Entity) -> None:

        if entity.has(SkillTargetAction):
            entity.remove(SkillTargetAction)

        if entity.has(SkillAction):
            entity.remove(SkillAction)

        if entity.has(SkillPropAction):
            entity.remove(SkillPropAction)

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
        entity.add(
            SkillTargetAction, safe_name, SkillTargetAction.__name__, list(targets)
        )

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
        entity.add(SkillPropAction, safe_name, SkillPropAction.__name__, prop_names)

    ######################################################################################################################################################
    def on_behavior_check_event(
        self, entity: Entity, behavior_sentence: str, allow: bool
    ) -> None:

        self._context.add_agent_context_message(
            set({entity}),
            builtin_prompt.make_behavior_check_prompt(
                self._context.safe_get_entity_name(entity), behavior_sentence, allow
            ),
        )

    ######################################################################################################################################################
