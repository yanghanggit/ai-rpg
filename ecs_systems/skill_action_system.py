from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from ecs_systems.action_components import (
    BehaviorAction,
    SkillTargetAction,
    SkillAction,
    PropAction,
    TagAction,
    PolishingStoryAction,
)
from ecs_systems.components import (
    AppearanceComponent,
    RPGCurrentWeaponComponent,
    RPGCurrentClothesComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, Any, Dict, List, cast, Optional, Set
from loguru import logger
from file_system.files_def import PropFile
from build_game.data_model import PropModel
import json
import ecs_systems.cn_builtin_prompt as builtin_prompt
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask
from my_agent.agent_plan import AgentPlan
from ecs_systems.cn_constant_prompt import _CNConstantPrompt_


class WorldDetermineSkillEnablePlan(AgentPlan):

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def result(self) -> str:
        tip_action = self.get_by_key(TagAction.__name__)
        if tip_action is None or len(tip_action.values) == 0:
            return _CNConstantPrompt_.FAILURE
        return tip_action.values[0]

    @property
    def polishing_story(self) -> str:
        polishing_story_action = self.get_by_key(PolishingStoryAction.__name__)
        if polishing_story_action is None or len(polishing_story_action.values) == 0:
            return ""
        return " ".join(polishing_story_action.values)


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
        return entity.has(SkillAction) and entity.has(SkillTargetAction)

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ######################################################################################################################################################
    def handle(self, entity: Entity) -> None:

        assert entity.has(SkillAction) and entity.has(SkillTargetAction)

        world_entity = self._context.get_world_entity(self._world_system_name)
        if world_entity is None:
            logger.warning(f"{self._world_system_name}, world_entity is None.")
            return

        appearance = self.get_appearance(entity)

        skill_files = self.get_skill_files(entity)

        prop_files = self.get_prop_files(entity)
        prop_files.extend(self.get_current_using_prop(entity))

        determine_skill_enable_ret = self.world_determine_skill_enable(
            entity, world_entity, appearance, skill_files, prop_files
        )

        if determine_skill_enable_ret is None:
            logger.debug(
                f"{self._world_system_name}, determine_skill_enable_ret is None."
            )
            return

        if not determine_skill_enable_ret.result:
            logger.debug(
                f"{self._world_system_name}, determine_skill_enable_ret.result is False."
            )
            return

        for target in self.get_targets(entity):
            self.release_skill(
                entity,
                target,
                appearance,
                skill_files,
                prop_files,
                determine_skill_enable_ret,
            )

    ######################################################################################################################################################
    def get_targets(self, entity: Entity) -> Set[Entity]:
        assert entity.has(SkillTargetAction)
        targets = set()
        for target_name in entity.get(SkillTargetAction).values:
            target = self._context.get_entity_by_name(target_name)
            if target is not None:
                targets.add(target)
        return targets

    ######################################################################################################################################################
    def release_skill(
        self,
        entity: Entity,
        target: Entity,
        appearance: str,
        skill_files: List[PropFile],
        prop_files: List[PropFile],
        world_determine_plan: WorldDetermineSkillEnablePlan,
    ) -> None:

        logger.debug(
            f"release_skill: {self._context.safe_get_entity_name(entity)} -> {self._context.safe_get_entity_name(target)}"
        )

        agent_name = self._context.safe_get_entity_name(target)
        agent = self._context._langserve_agent_system.get_agent(agent_name)
        if agent is None:
            return

        prompt = builtin_prompt.release_skill_prompt(
            self._context.safe_get_entity_name(entity),
            appearance,
            skill_files,
            prop_files,
            world_determine_plan.polishing_story,
        )

        logger.debug(prompt)
        task = LangServeAgentRequestTask.create(agent, prompt)
        if task is None:
            return None

        response = task.request()
        if response is None:
            return None

        plan = AgentPlan(agent._name, response)
        logger.debug(plan)

    ######################################################################################################################################################
    def world_determine_skill_enable(
        self,
        entity: Entity,
        world_entity: Entity,
        appearance: str,
        skill_files: List[PropFile],
        prop_files: List[PropFile],
    ) -> Optional[WorldDetermineSkillEnablePlan]:

        # 生成提示
        prompt = builtin_prompt.world_determine_skill_enable_prompt(
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

        task = LangServeAgentRequestTask.create_without_any_context(agent, prompt)
        if task is None:
            return None

        response = task.request()
        if response is None:
            return None

        plan = WorldDetermineSkillEnablePlan(agent._name, response)
        logger.debug(plan.result)
        logger.debug(plan.polishing_story)
        return plan

    ######################################################################################################################################################
    def get_skill_files(self, entity: Entity) -> List[PropFile]:
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

        fake_skill_file = self.fake_skill(safe_name)
        ret.append(fake_skill_file)

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
