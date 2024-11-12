from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from my_components.action_components import (
    SkillAction,
)
from my_components.components import (
    StageComponent,
    WeaponComponent,
    SkillComponent,
    ActorComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override, Set, Optional, List
from extended_systems.prop_file import PropFile
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent
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
class InternalParser:
    def __init__(self, command: str) -> None:
        self._origin_command = str(command)
        self._target: Set[str] = set()
        self._skill_prop_files: List[PropFile] = []
        self._skill_accessory_prop_files: List[tuple[PropFile, int]] = []

    ######################################################################################################################################################
    @property
    def origin_command(self) -> str:
        return self._origin_command

    ######################################################################################################################################################
    @property
    def commands(self) -> List[str]:
        return self._origin_command.split(" ")

    ######################################################################################################################################################
    @property
    def first_skill_name(self) -> str:
        if len(self._skill_prop_files) == 0:
            return ""
        return self._skill_prop_files[0].name

    ######################################################################################################################################################
    def parse(
        self,
        stage_name: str,
        actors_in_stage: Set[str],
        skill_prop_files: Set[PropFile],
        accessory_prop_files: Set[PropFile],
    ) -> None:

        # 添加目标
        for split_command in self.commands:
            self._process_command(
                split_command=split_command,
                stage_name=stage_name,
                actors_in_stage=actors_in_stage,
                skill_prop_files=skill_prop_files,
                accessory_prop_files=accessory_prop_files,
            )

        # 有场景就保留场景
        if stage_name in self._target:
            # 有场景就保留场景
            self._target.clear()
            self._target.add(stage_name)

        if len(self._skill_prop_files) > 1:
            # 只要一个技能
            self._skill_prop_files = self._skill_prop_files[:1]

    ######################################################################################################################################################
    def _process_command(
        self,
        split_command: str,
        stage_name: str,
        actors_in_stage: Set[str],
        skill_prop_files: Set[PropFile],
        accessory_prop_files: Set[PropFile],
    ) -> None:

        # 分析目标
        if stage_name in split_command:
            self._target.add(stage_name)
        else:
            for actor_name in actors_in_stage:
                if actor_name in split_command:
                    self._target.add(actor_name)

        # 分析使用的技能
        for skill_prop in skill_prop_files:
            if skill_prop.name in split_command and skill_prop.is_skill:
                self._skill_prop_files.append(skill_prop)

        # 分析技能配件
        for accessory_prop_file in accessory_prop_files:
            if accessory_prop_file.name not in split_command:
                continue

            if accessory_prop_file.is_skill:
                continue

            prop_name, count = (
                my_format_string.editor_prop_info_string.extract_prop_name_and_count(
                    split_command
                )
            )
            assert prop_name == accessory_prop_file.name
            logger.debug(f"{split_command}, prop_name: {prop_name}, count: {count}")
            self._skill_accessory_prop_files.append((accessory_prop_file, count))

    ######################################################################################################################################################


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################
@final
class SkillInvocationSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SkillAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SkillAction) and entity.has(ActorComponent)

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_skill_invocation(entity)

    ######################################################################################################################################################
    def _process_skill_invocation(self, actor_entity: Entity) -> None:

        # /skill 对@冀州.中山.卢奴.秘密监狱.火字十一号牢房的铁栏门上面的/腐化的木牌 使用技能/妖法.飞炎咒 消耗/A=1 消耗/B 消耗/C=2
        skill_invocation_action = actor_entity.get(SkillAction)
        if skill_invocation_action is None or len(skill_invocation_action.values) == 0:
            return

        skill_invocation_command = skill_invocation_action.values[0]

        # 帮助类
        skill_invocation_parser = InternalParser(skill_invocation_command)
        skill_invocation_parser.parse(
            self._get_current_stage_name(actor_entity),
            self._context.get_actor_names_in_stage(actor_entity),
            self._get_skill_prop_files(actor_entity),
            self._get_skill_accessory_prop_files(actor_entity),
        )

        # 判断合理性
        if (
            len(skill_invocation_parser._target) == 0
            or len(skill_invocation_parser._skill_prop_files) == 0
        ):
            self._on_skill_invocation_result_event(
                actor_entity, skill_invocation_command, False
            )
            # 不用继续了，没有技能或者没有目标
            return

        weapon_prop = self._get_weapon_prop_file(actor_entity)
        if weapon_prop is not None:
            # 默认会添加当前武器
            skill_invocation_parser._skill_accessory_prop_files.append((weapon_prop, 1))

        # 检查道具的消耗数量，是否满足
        for (
            skill_accessory_prop_file_info
        ) in skill_invocation_parser._skill_accessory_prop_files:
            prop_file, consume_count = skill_accessory_prop_file_info
            if prop_file.count < consume_count:
                self._on_skill_invocation_result_event(
                    actor_entity, skill_invocation_command, False
                )
                # 消耗的道具不够，不能执行。
                return

        # 创建技能实体
        self._create_skill_entity(actor_entity, skill_invocation_parser)

        # 事件通知
        self._on_skill_invocation_result_event(
            actor_entity, skill_invocation_parser.origin_command, True
        )

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
    def _create_skill_entity(
        self,
        entity: Entity,
        skill_invocation_parser: InternalParser,
    ) -> Entity:

        # 角色名字
        actor_name = self._context.safe_get_entity_name(entity)

        # 场景名字
        stage_entity = self._context.safe_get_stage_entity(entity)
        assert stage_entity is not None
        stage_name = self._context.safe_get_entity_name(stage_entity)

        # 组织技能配件的道具
        skill_accessory_props: List[str] = []
        for (
            skill_accessory_prop_file_info
        ) in skill_invocation_parser._skill_accessory_prop_files:
            skill_accessory_prop_file, consume_count = skill_accessory_prop_file_info
            skill_accessory_props.append(
                my_format_string.editor_prop_info_string.generate_prop_name_and_count_format_string(
                    skill_accessory_prop_file.name, consume_count
                )
            )

        # # 创建实体
        skill_entity = self._context.create_entity()

        # 添加组件
        skill_entity.add(
            SkillComponent,
            actor_name,
            skill_invocation_parser.origin_command,
            skill_invocation_parser.first_skill_name,
            stage_name,
            list(skill_invocation_parser._target),
            skill_accessory_props,
            "",
            "",
        )

        return skill_entity

    ######################################################################################################################################################
