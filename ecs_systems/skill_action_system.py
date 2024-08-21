from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from ecs_systems.action_components import (
    BehaviorAction,
    TargetAction,
    SkillAction,
    PropAction,
)
from ecs_systems.components import (
    AppearanceComponent,
    RPGCurrentWeaponComponent,
    RPGCurrentClothesComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, Any, Dict, List, cast
from loguru import logger
from file_system.files_def import PropFile
from build_game.data_model import PropModel
import json
import ecs_systems.cn_builtin_prompt as builtin_prompt
from my_agent.lang_serve_agent_request_task import LangServeAgentRequestTask


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
        return entity.has(SkillAction) and entity.has(TargetAction)

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ######################################################################################################################################################
    def handle(self, entity: Entity) -> None:
        assert entity.has(SkillAction) and entity.has(TargetAction)

        appearance = self.get_appearance(entity)

        skill_files = self.get_skill_files(entity)
        skill_prompt = self.make_skill_prompt(skill_files)

        prop_files = self.get_prop_files(entity)
        prop_files.extend(self.get_current_using_prop(entity))
        prop_prompt = self.make_prop_prompt(prop_files)

        safe_name = self._context.safe_get_entity_name(entity)

        prompt = f"""# {safe_name} 准备使用技能，请你判断是否有效。

## {safe_name} 信息
{appearance}
        
## 施放技能
{"\n".join(skill_prompt)}

## 使用道具
{"\n".join(prop_prompt)}

## 判断步骤
1. 结合 {safe_name} 信息 与 施放技能。判断其是否可以满足释放技能的条件。如果可以，则进行下一步。
2. 如果有 使用道具。则代表 在释放技能中，使用了道具作为辅助。例如: 触媒，消耗品，强化等，武器或者衣服。在道具信息中如果没有对技能释放有帮助的信息，可以忽略。
3. 如果没有 使用道具。则直接进行技能释放。

## 输出结果
- 如果技能释放成功，请输输出: </成功> 或者 </大成功>，否则请输出: </失败> 或者 </大失败>。
    - </大成功> 代表技能释放成功，且效果超出预期。
    - </大失败> 代表技能释放失败，使用者会受到惩罚。
    - 为了提高游戏性，请根据 {safe_name} 信息，施放技能，使用道具，来判断技能释放的结果。
- 在技能释放成功的情况下，结合以上所有信息，输出逻辑合理且附带润色的句子描述，来表达 {safe_name} 使用技能的释放结果。
    - 例句：{safe_name} 使用了 xx技能， 效果为xxx(逻辑合理且附带润色)。
"""

        logger.debug(prompt)

        world_entity = self._context.get_world_entity(self._world_system_name)
        if world_entity is None:
            # 没有这个对象，就认为这个系统不成立。
            logger.warning(f"{self._world_system_name}, world_entity is None.")
            return

        safe_name = self._context.safe_get_entity_name(world_entity)

        agent = self._context._langserve_agent_system.get_agent(safe_name)
        if agent is None:
            return

        task = LangServeAgentRequestTask.create_without_any_context(agent, prompt)
        if task is None:
            return

        response = task.request()
        if response is None:
            return

        logger.debug(response)

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

        fake_skill_file = self.fake_skill(safe_name)
        ret.append(fake_skill_file)

        return ret

    ######################################################################################################################################################
    def make_skill_prompt(self, skill_files: List[PropFile]) -> List[str]:
        ret: List[str] = []
        for skill_file in skill_files:
            prompt = builtin_prompt.prop_prompt(skill_file, True, False)
            ret.append(prompt)
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
    def make_prop_prompt(self, prop_files: List[PropFile]) -> List[str]:
        ret: List[str] = []
        for prop_file in prop_files:
            prompt = builtin_prompt.prop_prompt(prop_file, True, True)
            ret.append(prompt)
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
