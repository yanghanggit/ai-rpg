from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from my_components.action_components import (
    SkillAction,
    EquipPropAction,
)
from my_components.components import (
    SkillComponent,
    ActorComponent,
    WeaponDirectAttackSkill,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import Final, final, override, Set, List, Dict, Optional
from extended_systems.prop_file import PropFile
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent
import my_format_string.complex_prop_name
from loguru import logger
from gameplay_systems.actor_entity_utils import ActorStatusEvaluator
from my_models.entity_models import Attributes
import gameplay_systems.prompt_utils
import my_format_string.complex_prop_name
from my_models.file_models import PropSkillUsageMode


################################################################################################################################################
def _generate_skill_invocation_result_prompt(
    actor_name: str,
    initial_skill_command: str,
    adjusted_skill_command: str,
    processed_result: bool,
) -> str:

    if not processed_result:
        return f"""# 提示: {actor_name} 计划执行动作: {SkillAction.__name__}，结果为：系统经过判断后，否决。
## 输入的错误的 技能指令 如下:
{initial_skill_command}    
## 请分析问题，并再次理解规则:
{gameplay_systems.prompt_utils.skill_action_rule_prompt()}"""

    if initial_skill_command == adjusted_skill_command:
        return f"""# 提示: {actor_name} 计划执行动作: {SkillAction.__name__}，结果为：系统经过判断后，允许继续，并执行下一步判断。
    ## 输入的起效的 技能指令 如下:
    {initial_skill_command}"""

    return f"""# 提示: {actor_name} 计划执行动作: {SkillAction.__name__}，结果为：系统经过判断，并做了调整之后，允许继续，并执行下一步判断。
## 输入的 技能指令 如下:
{initial_skill_command}
## 系统调整后的 技能指令 如下:
{adjusted_skill_command}"""


######################################################################################################################################################
def _generate_weapon_count_exceed_prompt(
    actor_name: str,
    initial_skill_command: str,
    weapon_prop_file_names: List[str],
) -> str:
    return f"""# 提示: {actor_name} 计划执行动作: {SkillAction.__name__}，结果为：系统经过判断后，否决。
## 输入的错误的 技能指令 如下:
{initial_skill_command}  
## 请分析问题，并再次理解规则:
{gameplay_systems.prompt_utils.skill_action_rule_prompt()}
## 配置的武器数量过多，只能配置一个武器，但是配置了多个武器如下:
{";".join(weapon_prop_file_names)}"""


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################
@final
class SkillCommandParser:
    def __init__(
        self,
        context: RPGEntitasContext,
        input_skill_command: str,
        actor_status_evaluator: ActorStatusEvaluator,
    ) -> None:
        self._context: Final[RPGEntitasContext] = context
        self._actor_status_evaluator: Final[ActorStatusEvaluator] = (
            actor_status_evaluator
        )
        self._input_skill_command: Final[str] = str(input_skill_command)
        self._parsed_mapping: Dict[str, str] = {}
        self._parsed_skill_prop_files: List[PropFile] = []
        self._parsed_skill_accessory_prop_files: List[tuple[PropFile, int]] = []

        #
        stage_entity = self._context.get_stage_entity(actor_status_evaluator.stage_name)
        assert (
            stage_entity is not None
        ), f"stage_entity is None: {actor_status_evaluator.stage_name}"

        self.parse(
            actor_status_evaluator.stage_name,
            self._context.retrieve_actor_names_on_stage(stage_entity),
            set(actor_status_evaluator.skill_prop_files),
            set(actor_status_evaluator.available_skill_accessory_prop_files),
        )

    ######################################################################################################################################################
    @property
    def target_entities(self) -> Set[Entity]:
        ret: Set[Entity] = set()
        for target_name in self._parsed_mapping.keys():
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
    def output_skill_command(self) -> str:
        # 格式示例：@目标角色(全名);/技能道具(全名);/配置道具(全名)=消耗数量;/配置道具(全名)=消耗数量;...
        data: List[str] = []
        for target_entity_name in self.target_entity_names:
            data.append(f"""@{target_entity_name}""")

        for skill_prop in self._parsed_skill_prop_files:
            data.append(f"""/{skill_prop.name}""")

        for skill_accessory_prop_file_info in self._parsed_skill_accessory_prop_files:
            skill_accessory_prop_file, consume_count = skill_accessory_prop_file_info
            data.append(
                my_format_string.complex_prop_name.format_prop_name_with_count(
                    skill_accessory_prop_file.name, consume_count
                )
            )

        return ";".join(data)

    ######################################################################################################################################################
    @property
    def command_queue(self) -> List[str]:
        symbol = ";"
        if not symbol in self._input_skill_command:
            return []
        return self._input_skill_command.split(symbol)

    ######################################################################################################################################################
    @property
    def skill_name(self) -> str:
        if len(self._parsed_skill_prop_files) == 0:
            return ""
        return self._parsed_skill_prop_files[0].name

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
        if stage_name in self._parsed_mapping:
            self._parsed_mapping = {stage_name: self._parsed_mapping[stage_name]}

        if len(self._parsed_skill_prop_files) > 1:
            # 只要一个技能
            self._parsed_skill_prop_files = self._parsed_skill_prop_files[:1]

        # 是单体技能，只能有一个目标，就保留一个目标
        if (
            len(self._parsed_skill_prop_files) > 0
            and PropSkillUsageMode.SINGLE_TARGET_TAG
            in self._parsed_skill_prop_files[0].appearance
        ):
            if len(self._parsed_mapping) > 1:
                fisrt_key = ""
                first_value = ""
                for k, v in self._parsed_mapping.items():
                    fisrt_key = k
                    first_value = v
                    break
                self._parsed_mapping = {fisrt_key: first_value}

    ######################################################################################################################################################
    def _match_target_entity_name(self, check_name: str, target_name: str) -> bool:
        return f"""@{check_name}""" == target_name

    ######################################################################################################################################################
    def _match_prop_name(self, check_name: str, complex_prop_name: str) -> bool:
        prop_name, consume_count = (
            my_format_string.complex_prop_name.parse_complex_prop_info_string(
                complex_prop_name
            )
        )
        return check_name == prop_name

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
        if self._match_target_entity_name(stage_name, parsed_command):
            self._parsed_mapping.setdefault(stage_name, parsed_command)
        else:
            for actor_name in actors_on_stage:
                if self._match_target_entity_name(actor_name, parsed_command):
                    self._parsed_mapping.setdefault(actor_name, parsed_command)

        # 分析使用的技能
        for skill_prop in skill_prop_files:
            assert skill_prop.is_skill
            if self._match_prop_name(skill_prop.name, parsed_command):
                self._parsed_skill_prop_files.append(skill_prop)

        # 分析技能配件
        for accessory_prop_file in accessory_prop_files:
            if not self._match_prop_name(accessory_prop_file.name, parsed_command):
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
            self._parsed_skill_accessory_prop_files.append(
                (accessory_prop_file, consume_count)
            )

    ######################################################################################################################################################
    @property
    def accessory_weapon_prop_files(self) -> List[PropFile]:

        ret: List[PropFile] = []
        for skill_accessory_prop_file_info in self._parsed_skill_accessory_prop_files:
            skill_accessory_prop_file, consume_count = skill_accessory_prop_file_info
            if skill_accessory_prop_file.is_weapon:
                ret.append(skill_accessory_prop_file)
        return ret

    ######################################################################################################################################################
    @property
    def is_using_single_weapon(self) -> bool:
        current_weapon = self._actor_status_evaluator._current_weapon
        return (
            len(self.accessory_weapon_prop_files) == 1
            and current_weapon is not None
            and current_weapon == self.accessory_weapon_prop_files[0]
        )

    ######################################################################################################################################################
    @property
    def has_insight_info(self) -> bool:
        if len(self._parsed_skill_prop_files) == 0:
            return False
        return self._parsed_skill_prop_files[0].insight != ""

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
    def _extract_command_from_skill_action(self, actor_entity: Entity) -> str:
        skill_invocation_action = actor_entity.get(SkillAction)
        if skill_invocation_action is None or len(skill_invocation_action.values) == 0:
            return ""

        return skill_invocation_action.values[0]

    ######################################################################################################################################################
    def _process_skill_invocation(self, actor_entity: Entity) -> None:

        # 提取内容
        input_skill_command = self._extract_command_from_skill_action(actor_entity)
        if input_skill_command == "":
            logger.error("origin_command_from_skill_action is empty")
            self._notify_skill_invocation_result(
                actor_entity, input_skill_command, "", False
            )
            # 不用继续了，没有技能或者没有目标
            return

        # 帮助类分析整个字符串
        actor_status_evaluator = ActorStatusEvaluator(self._context, actor_entity)
        skill_command_parser = SkillCommandParser(
            context=self._context,
            input_skill_command=input_skill_command,
            actor_status_evaluator=actor_status_evaluator,
        )

        # 判断合理性
        if (
            len(skill_command_parser.target_entities) == 0
            or len(skill_command_parser._parsed_skill_prop_files) == 0
        ):
            # 不用继续了，没有技能或者没有目标，是不合理的。
            self._notify_skill_invocation_result(
                actor_entity, input_skill_command, "", False
            )
            return

        # 配置的武器多余一个。
        if len(skill_command_parser.accessory_weapon_prop_files) > 1:
            # 目前的规则配置武器太多不可以。就一次只能一个，如果不是当前装备的，就在后面做自动切换
            self._notify_weapon_count_exceed(
                actor_entity=actor_entity,
                initial_skill_command=input_skill_command,
                accessory_weapon_prop_files=skill_command_parser.accessory_weapon_prop_files,
            )
            return

        # 检查技能消耗的配件, 是否满足数量
        for (
            prop_file,
            consume_count,
        ) in skill_command_parser._parsed_skill_accessory_prop_files:
            if prop_file.count < consume_count:
                self._notify_skill_invocation_result(
                    entity=actor_entity,
                    initial_skill_command=input_skill_command,
                    adjusted_skill_command="",
                    processed_result=False,
                )
                # 消耗的道具不够，不能执行。
                return

        # 下面就不能停止了------------------------------------------------

        # 自动切换武器
        self._auto_switch_weapon(
            actor_entity,
            skill_command_parser.accessory_weapon_prop_files,
            actor_status_evaluator._current_weapon,
        )

        # 创建技能实体
        self._create_skill_entity(actor_entity, skill_command_parser)

        # 事件通知
        self._notify_skill_invocation_result(
            actor_entity,
            input_skill_command,
            skill_command_parser.output_skill_command,
            True,
        )

    ######################################################################################################################################################
    def _auto_switch_weapon(
        self,
        actor_entity: Entity,
        accessory_weapon_prop_files: List[PropFile],
        current_weapon: Optional[PropFile],
    ) -> bool:
        if len(accessory_weapon_prop_files) == 0:
            return False

        selected_accessory_weapon = accessory_weapon_prop_files[0]
        assert selected_accessory_weapon.is_weapon
        if selected_accessory_weapon == current_weapon:
            return False

        actor_entity.replace(
            EquipPropAction,
            selected_accessory_weapon.owner_name,
            [selected_accessory_weapon.name],
        )

        return True

    ######################################################################################################################################################
    def _notify_weapon_count_exceed(
        self,
        actor_entity: Entity,
        initial_skill_command: str,
        accessory_weapon_prop_files: List[PropFile],
    ) -> None:

        assert len(accessory_weapon_prop_files) > 1

        # 需要给到agent
        self._context.notify_event(
            entities=set({actor_entity}),
            agent_event=AgentEvent(
                message=_generate_weapon_count_exceed_prompt(
                    actor_name=self._context.safe_get_entity_name(actor_entity),
                    initial_skill_command=initial_skill_command,
                    weapon_prop_file_names=[
                        weapon_prop_file.name
                        for weapon_prop_file in accessory_weapon_prop_files
                    ],
                )
            ),
            keep_original_message_content=True,
        )

    ######################################################################################################################################################
    def _notify_skill_invocation_result(
        self,
        entity: Entity,
        initial_skill_command: str,
        adjusted_skill_command: str,
        processed_result: bool,
    ) -> None:

        # 需要给到agent
        self._context.notify_event(
            entities=set({entity}),
            agent_event=AgentEvent(
                message=_generate_skill_invocation_result_prompt(
                    actor_name=self._context.safe_get_entity_name(entity),
                    initial_skill_command=initial_skill_command,
                    adjusted_skill_command=adjusted_skill_command,
                    processed_result=processed_result,
                )
            ),
            keep_original_message_content=True,
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
        ) in skill_command_parser._parsed_skill_accessory_prop_files:
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
            skill_command_parser.output_skill_command,
            skill_command_parser.skill_name,
            stage_name,
            skill_command_parser.target_entity_names,
            skill_accessory_props,
            "",
            "",
            Attributes.BASE_VALUE_SCALE,
        )

        if (
            skill_command_parser.is_using_single_weapon
            and not skill_command_parser.has_insight_info
        ):
            # 直接技能。
            skill_entity.add(
                WeaponDirectAttackSkill, actor_name, skill_command_parser.skill_name
            )

        logger.debug(
            f"_create_skill_entity skill_comp: {skill_entity.get(SkillComponent)._asdict()}"
        )
        return skill_entity

    ######################################################################################################################################################
