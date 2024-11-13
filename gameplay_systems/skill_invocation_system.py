from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from my_components.action_components import (
    SkillAction,
)
from my_components.components import (
    SkillComponent,
    ActorComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import final, override, Set, List
from extended_systems.prop_file import PropFile
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent
import my_format_string.editor_prop_info_string
from loguru import logger
from gameplay_systems.actor_checker import ActorChecker
from my_models.file_models import PropType

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
class SkillCommandParser:
    def __init__(self, origin_command: str) -> None:
        self._origin_command = str(origin_command)
        self._target: Set[str] = set()
        self._skill_prop_files: List[PropFile] = []
        self._skill_accessory_prop_files: List[tuple[PropFile, int]] = []

    ######################################################################################################################################################
    @property
    def origin_command(self) -> str:
        return self._origin_command

    ######################################################################################################################################################
    @property
    def command_queue(self) -> List[str]:
        return self._origin_command.split(" ")

    ######################################################################################################################################################
    @property
    def skill_name(self) -> str:
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
        for parsed_command in self.command_queue:
            self._parse_command(
                parsed_command=parsed_command,
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
    def _parse_command(
        self,
        parsed_command: str,
        stage_name: str,
        actors_in_stage: Set[str],
        skill_prop_files: Set[PropFile],
        accessory_prop_files: Set[PropFile],
    ) -> None:

        # 分析目标
        if stage_name in parsed_command:
            self._target.add(stage_name)
        else:
            for actor_name in actors_in_stage:
                if actor_name in parsed_command:
                    self._target.add(actor_name)

        # 分析使用的技能
        for skill_prop in skill_prop_files:
            assert skill_prop.is_skill
            if skill_prop.name in parsed_command and skill_prop.is_skill:
                self._skill_prop_files.append(skill_prop)

        # 分析技能配件
        for accessory_prop_file in accessory_prop_files:
            if accessory_prop_file.name not in parsed_command:
                continue

            is_accessory_valid = (
                accessory_prop_file.is_special
                or accessory_prop_file.is_non_consumable_item
                or accessory_prop_file.is_consumable_item
            )
            assert is_accessory_valid
            if not is_accessory_valid:
                continue

            prop_name, consume_count = (
                my_format_string.editor_prop_info_string.extract_prop_name_and_count(
                    parsed_command
                )
            )
            assert prop_name == accessory_prop_file.name
            logger.debug(
                f"{parsed_command}, prop_name: {prop_name}, count: {consume_count}"
            )
            self._skill_accessory_prop_files.append(
                (accessory_prop_file, consume_count)
            )

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
    def _extract_origin_command_from_skill_action(self, actor_entity: Entity) -> str:
        skill_invocation_action = actor_entity.get(SkillAction)
        if skill_invocation_action is None or len(skill_invocation_action.values) == 0:
            return ""

        return skill_invocation_action.values[0]

    ######################################################################################################################################################
    def _process_skill_invocation(self, actor_entity: Entity) -> None:

        # /skill 对@冀州.中山.卢奴.秘密监狱.火字十一号牢房的铁栏门上面的/腐化的木牌 使用技能/妖法.飞炎咒 消耗/A=1 消耗/B 消耗/C=2
        origin_command_from_skill_action = (
            self._extract_origin_command_from_skill_action(actor_entity)
        )
        if origin_command_from_skill_action == "":
            logger.error("origin_command_from_skill_action is empty")
            self._notify_skill_invocation_result(
                actor_entity, origin_command_from_skill_action, False
            )
            # 不用继续了，没有技能或者没有目标
            return

        # 帮助类分析整个字符串
        check_self = ActorChecker(self._context, actor_entity)
        skill_command_parser = SkillCommandParser(origin_command_from_skill_action)
        skill_command_parser.parse(
            actor_entity.get(ActorComponent).current_stage,
            self._context.get_actor_names_in_stage(actor_entity),
            set(check_self.get_prop_files(PropType.TYPE_SKILL)),
            set(
                check_self.get_prop_files(PropType.TYPE_SPECIAL)
                + check_self.get_prop_files(PropType.TYPE_NON_CONSUMABLE_ITEM)
                + check_self.get_prop_files(PropType.TYPE_CONSUMABLE_ITEM)
            ),
        )

        # 判断合理性
        if (
            len(skill_command_parser._target) == 0
            or len(skill_command_parser._skill_prop_files) == 0
        ):
            # 不用继续了，没有技能或者没有目标
            self._notify_skill_invocation_result(
                actor_entity, origin_command_from_skill_action, False
            )
            return

        # 默认会添加当前武器到技能消耗配件中
        current_weapon = check_self._current_weapon
        if current_weapon is not None:

            if current_weapon not in [
                item[0] for item in skill_command_parser._skill_accessory_prop_files
            ]:
                skill_command_parser._skill_accessory_prop_files.append(
                    (current_weapon, 1)
                )

        # 检查技能消耗的配件, 是否满足数量
        for (
            skill_accessory_prop_file_info
        ) in skill_command_parser._skill_accessory_prop_files:
            prop_file, consume_count = skill_accessory_prop_file_info
            if prop_file.count < consume_count:
                self._notify_skill_invocation_result(
                    actor_entity, origin_command_from_skill_action, False
                )
                # 消耗的道具不够，不能执行。
                return

        # 创建技能实体
        self._create_skill_entity(actor_entity, skill_command_parser)

        # 事件通知
        self._notify_skill_invocation_result(
            actor_entity, skill_command_parser.origin_command, True
        )

    ######################################################################################################################################################
    def _notify_skill_invocation_result(
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
        skill_invocation_parser: SkillCommandParser,
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
            skill_invocation_parser.skill_name,
            stage_name,
            list(skill_invocation_parser._target),
            skill_accessory_props,
            "",
            "",
        )
        
        skill_comp = skill_entity.get(SkillComponent)
        logger.debug(f"_create_skill_entity skill_comp: {skill_comp._asdict()}")

        return skill_entity

    ######################################################################################################################################################
