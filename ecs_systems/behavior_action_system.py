from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from ecs_systems.action_components import (
    BehaviorAction,
    TargetAction,
    SkillAction,
    PropAction,
)
from ecs_systems.components import StageComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, Any, Dict, Set

# from loguru import logger
from file_system.files_def import PropFile
from build_game.data_model import PropModel
import json


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
    #
    def handle(self, entity: Entity) -> None:

        # /behavior 对@冀州.中山.卢奴.秘密监狱.火字十一号牢房的铁栏门  使用/飞炎咒
        behavior_action: BehaviorAction = entity.get(BehaviorAction)
        if len(behavior_action.values) == 0:
            return

        sentence = behavior_action.values[0]
        if sentence == "":
            return

        targets = self.parse_targets(entity, sentence)
        skills = self.parse_skills(entity, sentence)
        props = self.parse_props(entity, sentence)
        if len(targets) == 0 or len(skills) == 0:
            return

        self.clear_action(entity)
        self.add_target_action(entity, targets)
        self.add_skill_action(entity, skills)
        self.add_prop_action(entity, props)

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
        actor_names = self._context.actor_names_in_stage(current_stage_entity)
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
        skill_files.append(self.fake_skill(safe_name))

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
        entity.add(SkillAction, safe_name, SkillAction.__name__, list(skills))

    ######################################################################################################################################################
    def parse_props(self, entity: Entity, sentence: str) -> Set[PropFile]:
        return set()

    ######################################################################################################################################################
    def add_prop_action(self, entity: Entity, props: Set[PropFile]) -> None:
        if len(props) == 0:
            return
        safe_name = self._context.safe_get_entity_name(entity)
        entity.add(PropAction, safe_name, PropAction.__name__, list(props))

    ######################################################################################################################################################
    def fake_skill(self, owner_name: str) -> PropFile:

        fake_data: Dict[str, Any] = {
            "name": "飞炎咒",
            "codename": "flying_flame_curse",
            "description": "发射小型火球",
            "type": "Skill",
            "attributes": [0, 0, 1, 0],
            "appearance": "无",
        }

        prop_model = PropModel.model_validate_json(
            json.dumps(fake_data, ensure_ascii=False)
        )

        prop_file = PropFile(
            self._context._guid_generator.generate(),
            prop_model.name,
            owner_name,
            prop_model,
            1,
        )

        return prop_file

    ######################################################################################################################################################
