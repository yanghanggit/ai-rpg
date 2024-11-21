from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from my_components.action_components import (
    SkillAction,
)
from my_components.components import (
    SkillComponent,
    ActorComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import Final, final, override, Set, List, Dict
from extended_systems.prop_file import PropFile
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent
import my_format_string.complex_prop_name
from loguru import logger
from gameplay_systems.actor_entity_utils import ActorStatusEvaluator
from my_models.entity_models import Attributes
import gameplay_systems.prompt_utils


################################################################################################################################################
def _generate_skill_invocation_result_prompt(
    actor_name: str, skill_command: str, result: bool
) -> str:

    if not result:
        return f"""# 提示: {actor_name} 计划执行动作: {SkillAction.__name__}，结果为：系统经过判断后，否决。
## 输入的错误的 技能使用指令 如下:
{skill_command}    
## 请分析问题，并再次理解规则:
{gameplay_systems.prompt_utils.skill_action_rule_prompt()}"""

    return f"""# 提示: {actor_name} 计划执行动作: {SkillAction.__name__} ，结果为：系统经过判断后，允许继续，并执行下一步判断。
## 输入的起效的 技能使用指令 如下:
{skill_command}"""


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################


@final
class SkillCommandParser:
    def __init__(
        self, context: RPGEntitasContext, actor_name: str, skill_command: str
    ) -> None:
        self._context: Final[RPGEntitasContext] = context
        self._actor_name: Final[str] = actor_name
        self._skill_command: Final[str] = str(skill_command)
        self._parsed_command_mapping: Dict[str, str] = {}
        self._skill_prop_files: List[PropFile] = []
        self._skill_accessory_prop_files: List[tuple[PropFile, int]] = []

    ######################################################################################################################################################
    @property
    def target_entities(self) -> Set[Entity]:
        ret: Set[Entity] = set()
        for target_name in self._parsed_command_mapping.keys():
            target_entity = self._context.get_entity_by_name(target_name)
            if target_entity is not None:
                ret.add(target_entity)
        return ret

    ######################################################################################################################################################
    @property
    def target_entity_names(self) -> List[str]:
        ret: List[str] = []
        for entity in self.target_entities:
            ret.append(self._context.safe_get_entity_name(entity))
        return ret

    ######################################################################################################################################################
    @property
    def skill_command(self) -> str:
        return self._skill_command

    ######################################################################################################################################################
    @property
    def command_queue(self) -> List[str]:
        return self._skill_command.split(" ")

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
        actors_on_stage: Set[str],
        skill_prop_files: Set[PropFile],
        accessory_prop_files: Set[PropFile],
    ) -> None:

        # 添加目标
        for parsed_command in self.command_queue:
            self._parse_command(
                parsed_command=parsed_command,
                stage_name=stage_name,
                actors_on_stage=actors_on_stage,
                skill_prop_files=skill_prop_files,
                accessory_prop_files=accessory_prop_files,
            )

        # 有场景就保留场景
        if stage_name in self._parsed_command_mapping:
            self._parsed_command_mapping = {
                stage_name: self._parsed_command_mapping[stage_name]
            }

        if len(self._skill_prop_files) > 1:
            # 只要一个技能
            self._skill_prop_files = self._skill_prop_files[:1]

    ######################################################################################################################################################
    def _parse_command(
        self,
        parsed_command: str,
        stage_name: str,
        actors_on_stage: Set[str],
        skill_prop_files: Set[PropFile],
        accessory_prop_files: Set[PropFile],
    ) -> None:

        # 分析目标
        if stage_name in parsed_command:
            self._parsed_command_mapping.setdefault(stage_name, parsed_command)
        else:
            for actor_name in actors_on_stage:
                if actor_name in parsed_command:
                    self._parsed_command_mapping.setdefault(actor_name, parsed_command)

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
                my_format_string.complex_prop_name.parse_complex_prop_info_string(
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
        actor_status_evaluator = ActorStatusEvaluator(self._context, actor_entity)
        skill_command_parser = SkillCommandParser(
            context=self._context,
            actor_name=actor_status_evaluator.actor_name,
            skill_command=origin_command_from_skill_action,
        )
        skill_command_parser.parse(
            actor_entity.get(ActorComponent).current_stage,
            self._context.retrieve_actor_names_on_stage(actor_entity),
            set(actor_status_evaluator.skill_prop_files),
            set(actor_status_evaluator.available_skill_accessory_prop_files),
        )

        # 判断合理性
        if (
            len(skill_command_parser.target_entities) == 0
            or len(skill_command_parser._skill_prop_files) == 0
        ):
            # 不用继续了，没有技能或者没有目标
            self._notify_skill_invocation_result(
                actor_entity, origin_command_from_skill_action, False
            )
            return

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
            actor_entity, origin_command_from_skill_action, True
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
        skill_command_parser: SkillCommandParser,
    ) -> Entity:

        # 角色
        actor_name = self._context.safe_get_entity_name(entity)

        # 场景
        stage_entity = self._context.safe_get_stage_entity(entity)
        assert stage_entity is not None
        stage_name = self._context.safe_get_entity_name(stage_entity)

        # 组织技能配件的道具
        skill_accessory_props: List[str] = []
        for (
            skill_accessory_prop_file_info
        ) in skill_command_parser._skill_accessory_prop_files:
            skill_accessory_prop_file, consume_count = skill_accessory_prop_file_info
            skill_accessory_props.append(
                my_format_string.complex_prop_name.format_prop_name_with_count(
                    skill_accessory_prop_file.name, consume_count
                )
            )

        skill_entity = self._context.create_entity()
        skill_entity.add(
            SkillComponent,
            actor_name,
            skill_command_parser.skill_command,
            skill_command_parser.skill_name,
            stage_name,
            skill_command_parser.target_entity_names,
            skill_accessory_props,
            "",
            "",
            Attributes.BASE_VALUE_SCALE,
        )

        logger.debug(
            f"_create_skill_entity skill_comp: {skill_entity.get(SkillComponent)._asdict()}"
        )
        return skill_entity

    ######################################################################################################################################################
