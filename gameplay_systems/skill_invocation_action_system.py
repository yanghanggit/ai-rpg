from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from my_components.action_components import (
    SkillInvocationAction,
    SkillTargetAction,
    SkillAction,
    SkillAccessoryAction,
)
from my_components.components import StageComponent, WeaponComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override, Set, Optional, List
from extended_systems.prop_file import PropFile
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent
import gameplay_systems.skill_system_utils
import my_format_string.editor_prop_info_string
from loguru import logger

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


# todo
class SkillInvocationHelper:
    def __init__(self, command: str) -> None:
        self._origin_command = str(command)
        self._target: Set[str] = set()
        self._skill_prop_files: List[PropFile] = []
        self._skill_accessory_prop_files: List[tuple[PropFile, int]] = []

    # /skillinvocation 对@冀州.中山.卢奴.秘密监狱.火字十一号牢房的铁栏门上面的/腐化的木牌 使用技能/妖法.飞炎咒 消耗/A#1 消耗/B 消耗/C#2
    ######################################################################################################################################################
    @property
    def commands(self) -> List[str]:
        return self._origin_command.split(" ")

    ######################################################################################################################################################
    def parse(
        self,
        stage_name: str,
        actors_in_stage: Set[str],
        skill_prop_files: Set[PropFile],
        accessory_prop_files: Set[PropFile],
    ) -> None:

        # 添加目标
        commands = self.commands

        # 分析目标
        if stage_name in commands:
            self._target.add(stage_name)
        else:
            for actor_name in actors_in_stage:
                if actor_name in commands:
                    self._target.add(actor_name)

        # 分析使用的技能
        for skill_prop in skill_prop_files:
            if skill_prop.name in commands and skill_prop.is_skill:
                self._skill_prop_files.append(skill_prop)
                break  # 只要一个!

        # 分析使用的道具
        for cmd in commands:
            for accessory_prop_file in accessory_prop_files:
                if accessory_prop_file.name not in cmd:
                    continue

                prop_name, count = (
                    my_format_string.editor_prop_info_string.extract_prop_name_and_count(
                        cmd
                    )
                )
                assert prop_name == accessory_prop_file.name
                logger.debug(f"{cmd}, prop_name: {prop_name}, count: {count}")
                self._skill_accessory_prop_files.append((accessory_prop_file, count))

    ######################################################################################################################################################


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

        # /skillinvocation 对@冀州.中山.卢奴.秘密监狱.火字十一号牢房的铁栏门上面的/腐化的木牌 使用技能/妖法.飞炎咒 消耗/A#1 消耗/B 消耗/C#2

        skill_invocation_command = (
            gameplay_systems.skill_system_utils.parse_skill_invocation_action_command(
                entity
            )
        )
        if skill_invocation_command == "":
            return

        # 帮助类
        helper = SkillInvocationHelper(skill_invocation_command)

        # 获得数据
        current_stage_name = self._get_current_stage_name(entity)
        actors_in_stage = self._context.get_actor_names_in_stage(entity)
        skill_prop_files = self._get_skill_prop_files(entity)
        skill_accessory_prop_files = self._get_skill_accessory_prop_files(entity)

        #
        helper.parse(
            current_stage_name,
            actors_in_stage,
            skill_prop_files,
            skill_accessory_prop_files,
        )

        # 不用继续了
        if len(helper._target) == 0 or len(helper._skill_prop_files) == 0:
            self._on_skill_invocation_result_event(
                entity, skill_invocation_command, False
            )
            return

        weapon_prop = self._get_weapon_prop_file(entity)
        if weapon_prop is not None:
            # 默认会添加当前武器
            helper._skill_accessory_prop_files.append((weapon_prop, 1))

        # 检查道具的消耗数量，是否满足
        for skill_accessory_prop_file_info in helper._skill_accessory_prop_files:
            prop_file, count = skill_accessory_prop_file_info
            if prop_file.count < count:
                self._on_skill_invocation_result_event(
                    entity, skill_invocation_command, False
                )
                return

        # 以上全过了，就开始 添加动作
        gameplay_systems.skill_system_utils.clear_skill_system_actions(entity)
        self._add_skill_target_action(entity, helper._target)
        self._add_skill_action(entity, set(helper._skill_prop_files))
        self._add_skill_accessory_prop_action(
            entity, helper._skill_accessory_prop_files
        )

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
    def _get_current_stage_name(self, entity: Entity) -> str:
        current_stage_entity = self._context.safe_get_stage_entity(entity)
        assert current_stage_entity is not None
        return current_stage_entity.get(StageComponent).name

    ######################################################################################################################################################
    def _get_skill_prop_files(self, entity: Entity) -> Set[PropFile]:

        safe_name = self._context.safe_get_entity_name(entity)
        skill_files = self._context._file_system.get_files(PropFile, safe_name)

        ret: Set[PropFile] = set()
        for skill_file in skill_files:
            if not skill_file.is_skill:
                continue
            ret.add(skill_file)

        return ret

    ######################################################################################################################################################
    def _get_skill_accessory_prop_files(self, entity: Entity) -> Set[PropFile]:

        safe_name = self._context.safe_get_entity_name(entity)
        prop_files = self._context._file_system.get_files(PropFile, safe_name)

        ret: Set[PropFile] = set()
        for prop_file in prop_files:
            if prop_file.is_skill:
                continue
            ret.add(prop_file)

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
    def _add_skill_action(
        self, entity: Entity, skill_prop_files: Set[PropFile]
    ) -> None:
        if len(skill_prop_files) == 0:
            return
        skill_names = [skill.name for skill in skill_prop_files]
        entity.add(SkillAction, self._context.safe_get_entity_name(entity), skill_names)

    ######################################################################################################################################################
    def _add_skill_accessory_prop_action(
        self, entity: Entity, skill_accessory_prop_files: List[tuple[PropFile, int]]
    ) -> None:
        if len(skill_accessory_prop_files) == 0:
            return

        action_params: List[str] = []
        for prop_file, count in skill_accessory_prop_files:
            action_params.append(
                my_format_string.editor_prop_info_string.generate_prop_name_and_count_format_string(
                    prop_file.name, count
                )
            )

        entity.add(
            SkillAccessoryAction,
            self._context.safe_get_entity_name(entity),
            action_params,
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
