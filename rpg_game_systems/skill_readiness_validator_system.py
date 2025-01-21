from entitas import Matcher, ExecuteProcessor, Entity  # type: ignore
from dataclasses import dataclass
from components.actions import (
    TagAction,
    MindVoiceAction,
    AnnounceAction,
)
from components.components import (
    SkillComponent,
    DestroyComponent,
    DirectSkillFlagComponent,
)
from game.rpg_game_context import RPGGameContext
from typing import final, override, List, Dict, Set
from loguru import logger
from extended_systems.prop_file import (
    PropFile,
    generate_skill_prop_file_prompt,
    generate_skill_accessory_prop_file_prompt,
)
import rpg_game_systems.prompt_utils
from agent.agent_request_handler import AgentRequestHandler
from agent.agent_response_handler import AgentResponseHandler
from game.rpg_game import RPGGame
import rpg_game_systems.skill_entity_utils
from agent.lang_serve_agent import LangServeAgent
from models.entity_models import Attributes
from models.file_models import PropSkillUsageMode
import rpg_game_systems.task_request_utils


################################################################################################################################################
def _generate_skill_readiness_validator_prompt(
    actor_name: str,
    skill_prop_files: List[PropFile],
    skill_accessory_prop_files: List[PropFile],
) -> str:

    assert len(skill_prop_files) == 1, "技能文件数量不为1"

    # 使用的技能！！！
    skill_prop_files_prompt: List[str] = []
    for skill_prop_file in skill_prop_files:
        assert skill_prop_file.is_skill, "不是技能文件"
        skill_prop_files_prompt.append(
            generate_skill_prop_file_prompt(skill_prop_file, False)
        )
    if len(skill_prop_files_prompt) == 0:
        skill_prop_files_prompt.append("无任何技能")
        assert False, "技能不能为空"

    # 配置的道具！！
    skill_accessory_prop_files_prompt: List[str] = []
    for skill_accessory_prop_file in skill_accessory_prop_files:
        skill_accessory_prop_files_prompt.append(
            generate_skill_accessory_prop_file_prompt(skill_accessory_prop_file)
        )
    if len(skill_accessory_prop_files_prompt) == 0:
        skill_accessory_prop_files_prompt.append("未配置任何道具")

    return f"""# 提示: {actor_name} 计划使用技能，需判断是否允许使用
## 技能信息
{"\n".join(skill_prop_files_prompt)}
## 配置的道具信息
{"\n".join(skill_accessory_prop_files_prompt)}
## 判断逻辑步骤
1. 技能条件检查：结合 {actor_name} 的状态和历史，检查技能信息是否符合释放条件。如不满足，技能释放失败，停止判断。
2. 配置道具条件检查：结合 {actor_name} 的状态和历史，验证配置道具是否符合使用条件。如不满足，技能释放失败，停止判断。
3. 配置道具分支判断：
    - 若有配置道具，综合技能与道具信息进行验证。如技能对配置道具有特定要求且道具不满足，技能释放失败，停止判断。
    - 若无配置道具，继续下一步。
4. 最终判断：如以上条件均满足，技能释放成功。
### 注意事项
上述的‘状态和历史’为角色的历史经历（事件与对话等）、性格特点、外貌特征(基础形态)等信息，用于判断技能释放条件。

## 成功技能事件描述
1. 如果成功，请注意 上述 技能信息 中的 技能表现的描述。其中 {PropSkillUsageMode.CASTER_TAG} 即为 {actor_name}。
2. {PropSkillUsageMode.SINGLE_TARGET_TAG} 或 {PropSkillUsageMode.MULTI_TARGETS_TAG} 为技能的目标。
3. 将描述做为例句模版，组织然后润色并输出 {actor_name} 使用技能时的事件描述。

## 输出要求
- 请遵循输出格式指南。
- 返回结果仅包含：{MindVoiceAction.__name__} 和 {TagAction.__name__}。
## 格式示例：
{{ 
    "{MindVoiceAction.__name__}":["输入你的最终判断结果，说明技能是否成功或失败。如果是失败就说明失败的原因。"], 
    "{AnnounceAction.__name__}": ["如成功，输出‘成功技能事件描述’（见上文），如失败，输出‘失败’"],
    "{TagAction.__name__}":["Yes/No"（技能是否成功）] 
}}"""


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################
@final
class InternalResponseHandler(AgentResponseHandler):

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def is_skill_ready(self) -> bool:
        return self._parse_boolean(TagAction.__name__)

    @property
    def inspector_content(self) -> str:
        if not self.is_skill_ready:
            return ""
        return self._concatenate_values(AnnounceAction.__name__)


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################
@dataclass
class InternalProcessData:
    actor_entity: Entity
    skill_entity: Entity
    agent: LangServeAgent
    agent_request_handler: AgentRequestHandler


######################################################################################################################################################
######################################################################################################################################################
######################################################################################################################################################
@final
class SkillReadinessValidatorSystem(ExecuteProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ######################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ######################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        # 只关注技能
        skill_entities = self._context.get_group(
            Matcher(all_of=[SkillComponent], none_of=[DestroyComponent])
        ).entities.copy()

        # 组成成方便的数据结构
        internal_process_data = self._initialize_internal_process_data(skill_entities)

        # 推理技能, 可能有一部分不需要处理
        await self._validate_skill_readiness(internal_process_data)

        # 后续处理
        self._process_agent_tasks(internal_process_data)

    ######################################################################################################################################################
    def _initialize_internal_process_data(
        self, skill_entities: Set[Entity]
    ) -> List[InternalProcessData]:

        ret: List[InternalProcessData] = []
        for skill_entity in skill_entities:
            skill_comp = skill_entity.get(SkillComponent)

            actor_entity = self._context.get_actor_entity(skill_comp.name)
            assert (
                actor_entity is not None
            ), f"actor_entity {skill_comp.name} not found."
            if actor_entity is None:
                logger.debug(f"actor_entity {skill_comp.name} not found.")
                continue

            agent = self._context.safe_get_agent(actor_entity)
            ret.append(
                InternalProcessData(
                    actor_entity=actor_entity,
                    skill_entity=skill_entity,
                    agent=agent,
                    agent_request_handler=AgentRequestHandler.create_without_context(
                        agent=agent, prompt=""
                    ),
                )
            )

        return ret

    ######################################################################################################################################################
    async def _validate_skill_readiness(
        self, internal_process_data: List[InternalProcessData]
    ) -> None:
        agent_tasks = self._generate_agent_tasks(internal_process_data)
        if len(agent_tasks) == 0:
            return
        await rpg_game_systems.task_request_utils.gather(
            [task for task in agent_tasks.values()]
        )

    ######################################################################################################################################################
    def _process_agent_tasks(
        self, internal_process_data_list: List[InternalProcessData]
    ) -> None:

        for process_data in internal_process_data_list:

            if not self._is_skill_ready(process_data):
                rpg_game_systems.skill_entity_utils.destroy_skill_entity(
                    process_data.skill_entity
                )
                continue

            skill_comp = process_data.skill_entity.get(SkillComponent)
            process_data.skill_entity.replace(
                SkillComponent,
                skill_comp.name,
                skill_comp.command,
                skill_comp.skill_name,
                skill_comp.stage,
                skill_comp.targets,
                skill_comp.skill_accessory_props,
                rpg_game_systems.prompt_utils.SkillResultPromptTag.SUCCESS,
                self._extract_inspector_content(process_data),
                Attributes.BASE_VALUE_SCALE,
            )

            # 标记直接技能
            if rpg_game_systems.skill_entity_utils.validate_direct_skill(
                self._context, process_data.skill_entity, process_data.actor_entity
            ):
                process_data.skill_entity.replace(
                    DirectSkillFlagComponent,
                    process_data.agent.name,
                    skill_comp.skill_name,
                )

    ######################################################################################################################################################
    def _is_skill_ready(self, process_data: InternalProcessData) -> bool:
        return InternalResponseHandler(
            process_data.agent_request_handler.agent_name,
            process_data.agent_request_handler.response_content,
        ).is_skill_ready

    ######################################################################################################################################################
    def _extract_inspector_content(self, process_data: InternalProcessData) -> str:

        if rpg_game_systems.skill_entity_utils.validate_direct_skill(
            self._context, process_data.skill_entity, process_data.actor_entity
        ):
            return rpg_game_systems.skill_entity_utils.format_direct_skill_inspector_content(
                self._context, process_data.skill_entity
            )

        return InternalResponseHandler(
            process_data.agent_request_handler.agent_name,
            process_data.agent_request_handler.response_content,
        ).inspector_content

    ######################################################################################################################################################
    def _generate_agent_tasks(
        self, internal_process_data: List[InternalProcessData]
    ) -> Dict[str, AgentRequestHandler]:

        ret: Dict[str, AgentRequestHandler] = {}

        for process_data in internal_process_data:

            assert process_data.actor_entity is not None, "actor_entity is None."
            assert process_data.skill_entity is not None, "skill_entity is None."
            assert process_data.agent is not None, "agent is None."

            skill_readiness_prompt = _generate_skill_readiness_validator_prompt(
                process_data.agent.name,
                rpg_game_systems.skill_entity_utils.parse_skill_prop_files(
                    context=self._context,
                    skill_entity=process_data.skill_entity,
                    actor_entity=process_data.actor_entity,
                ),
                rpg_game_systems.skill_entity_utils.retrieve_skill_accessory_prop_files(
                    context=self._context,
                    skill_entity=process_data.skill_entity,
                    actor_entity=process_data.actor_entity,
                ),
            )

            process_data.agent_request_handler = ret[process_data.agent.name] = (
                AgentRequestHandler.create_with_full_context(
                    process_data.agent,
                    rpg_game_systems.prompt_utils.replace_with_you(
                        skill_readiness_prompt, process_data.agent.name
                    ),
                )
            )

        return ret

    ######################################################################################################################################################
