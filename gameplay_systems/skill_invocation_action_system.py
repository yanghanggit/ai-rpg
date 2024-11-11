from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from my_components.action_components import (
    SkillInvocationAction,
    SkillTargetAction,
    SkillAction,
    SkillAccessoryAction,
    SkillWorldHarmonyInspectorAction,
)
from my_components.components import StageComponent, WeaponComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override, Set, Optional, Any
from extended_systems.prop_file import PropFile
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent


################################################################################################################################################


def _generate_skill_invocation_result_prompt(
    actor_name: str, command: str, result: bool
) -> str:
    if result:
        prompt1 = f"""# {actor_name} 准备发起一次使用技能的行动。
## 输入语句
{command}
## 分析过程
输入语句中应至少包含一个技能与一个目标。可以选择性的包含道具。
## 结果
系统经过分析之后允许了这次行动。"""
        return prompt1

    prompt2 = f""" #{actor_name} 准备发起一次使用技能的行动。
## 输入语句
{command}
## 分析过程
输入语句中应至少包含一个技能与一个目标。可以选择性的包含道具。
## 结果
- 注意！系统经过分析之后拒绝了这次行动。
- 请 {actor_name} 检查 输入语句。是否满足 分析过程 中提到的要求。"""

    return prompt2


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################


@final
class SkillInvocationActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SkillInvocationAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SkillInvocationAction)

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_skill_invocation(entity)

    ######################################################################################################################################################
    def _process_skill_invocation(self, entity: Entity) -> None:

        skill_invocation_action = entity.get(SkillInvocationAction)
        if len(skill_invocation_action.values) == 0:
            return

        skill_invocation_command = skill_invocation_action.values[0]
        if skill_invocation_command == "":
            return

        # 基础数据
        targets = self._parse_targets_from_command(entity, skill_invocation_command)
        skills = self._parse_skill_prop_files_from_command(
            entity, skill_invocation_command
        )
        # 不用继续了
        if len(targets) == 0 or len(skills) == 0:
            self._on_skill_invocation_result_event(
                entity, skill_invocation_command, False
            )
            return

        props = self._parse_skill_accessory_prop_files_from_command(
            entity, skill_invocation_command
        )

        # 默认会添加当前武器? 先不用。
        weapon_prop = self._get_weapon_prop_file(entity)
        if weapon_prop is not None:
            pass
            # props.add(weapon_prop)

        # 添加动作
        self._remove_action_components(entity)
        self._add_skill_target_action(entity, targets)
        self._add_skill_action(entity, skills)
        self._add_skill_accessory_prop_action(entity, props)

        # 事件通知
        self._on_skill_invocation_result_event(entity, skill_invocation_command, True)

    ######################################################################################################################################################
    def _get_weapon_prop_file(self, entity: Entity) -> Optional[PropFile]:
        if not entity.has(WeaponComponent):
            return None
        current_weapon_comp = entity.get(WeaponComponent)
        return self._context._file_system.get_file(
            PropFile, current_weapon_comp.name, current_weapon_comp.propname
        )

    ######################################################################################################################################################
    def _remove_action_components(
        self,
        entity: Entity,
        actions_comp: Set[type[Any]] = set(
            {
                SkillTargetAction,
                SkillAction,
                SkillAccessoryAction,
                SkillWorldHarmonyInspectorAction,
            }
        ),
    ) -> None:

        for action_comp in actions_comp:
            if entity.has(action_comp):
                entity.remove(action_comp)

    ######################################################################################################################################################
    def _parse_targets_from_command(self, entity: Entity, command: str) -> Set[str]:

        current_stage_entity = self._context.safe_get_stage_entity(entity)
        assert current_stage_entity is not None
        if current_stage_entity is None:
            return set()

        current_stage_name = current_stage_entity.get(StageComponent).name
        if current_stage_name in command:
            # 有场景就是直接是场景的。放弃下面的处理！
            return set({current_stage_name})

        ret: Set[str] = set()
        actor_names = self._context.get_actor_names_in_stage(current_stage_entity)
        for actor_name in actor_names:
            if actor_name in command:
                ret.add(actor_name)
        return ret

    ######################################################################################################################################################
    def _add_skill_target_action(self, entity: Entity, target_names: Set[str]) -> None:
        if len(target_names) == 0:
            return
        entity.add(
            SkillTargetAction,
            self._context.safe_get_entity_name(entity),
            list(target_names),
        )

    ######################################################################################################################################################
    def _parse_skill_prop_files_from_command(
        self, entity: Entity, command: str
    ) -> Set[PropFile]:

        safe_name = self._context.safe_get_entity_name(entity)
        skill_files = self._context._file_system.get_files(PropFile, safe_name)

        ret: Set[PropFile] = set()
        for skill_file in skill_files:
            if not skill_file.is_skill:
                continue

            if skill_file.name in command:
                ret.add(skill_file)

        return ret

    ######################################################################################################################################################
    def _add_skill_action(
        self, entity: Entity, prop_name_as_skill_name: Set[PropFile]
    ) -> None:
        if len(prop_name_as_skill_name) == 0:
            return
        skill_names = [skill.name for skill in prop_name_as_skill_name]
        entity.add(SkillAction, self._context.safe_get_entity_name(entity), skill_names)

    ######################################################################################################################################################
    def _parse_skill_accessory_prop_files_from_command(
        self, entity: Entity, command: str
    ) -> Set[PropFile]:

        safe_name = self._context.safe_get_entity_name(entity)
        prop_files = self._context._file_system.get_files(PropFile, safe_name)
        ret: Set[PropFile] = set()
        for prop_file in prop_files:
            if prop_file.is_skill:
                continue
            if prop_file.name in command:
                ret.add(prop_file)

        return ret

    ######################################################################################################################################################
    def _add_skill_accessory_prop_action(
        self, entity: Entity, props: Set[PropFile]
    ) -> None:
        if len(props) == 0:
            return
        prop_names = [prop.name for prop in props]
        entity.add(
            SkillAccessoryAction, self._context.safe_get_entity_name(entity), prop_names
        )

    ######################################################################################################################################################
    def _on_skill_invocation_result_event(
        self, entity: Entity, command: str, processed_result: bool
    ) -> None:

        # 需要给到agent
        self._context.notify_event(
            set({entity}),
            AgentEvent(
                message=_generate_skill_invocation_result_prompt(
                    self._context.safe_get_entity_name(entity),
                    command,
                    processed_result,
                )
            ),
        )

    ######################################################################################################################################################
