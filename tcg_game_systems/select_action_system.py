from pydantic import BaseModel
from entitas import Matcher, Entity, Matcher, GroupEvent  # type: ignore
from extended_systems.chat_request_handler import ChatRequestHandler
import format_string.json_format
from components.components_v_0_0_1 import (
    StageEnvironmentComponent,
    SkillCandidateQueueComponent,
)
from overrides import override
from typing import List, Set, final
from loguru import logger
from models.v_0_0_1 import Skill
from components.actions_v_0_0_1 import StageDirectorAction, SelectAction, TurnAction
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem


#######################################################################################################################################
@final
class SkillSelectionResponse(BaseModel):
    skill: str
    targets: List[str]
    reason: str
    interaction: str


#######################################################################################################################################
def _generate_prompt(
    current_stage: str,
    current_stage_narration: str,
    skill_candidates: List[Skill],
    action_order: List[str],
) -> str:

    skill_candidates1 = [skill.model_dump_json() for skill in skill_candidates]

    select_skill_response_example = SkillSelectionResponse(
        skill="技能名称",
        targets=["目标1", "目标2", "..."],
        reason="技能使用原因",
        interaction="在使用技能时你要表演的交互性动作或者说的话",
    )

    return f"""# 战斗正在进行，请考虑后，在技能列表中选择你将要使用的技能！
## 当前场景
{current_stage}
### 场景描述
{current_stage_narration}
## 技能列表
{"\n".join(skill_candidates1)}
## 场景内角色行动顺序(从左到右)
{action_order}
## 输出要求
- 不要使用```json```来封装内容。
### 输出格式(JSON)
{select_skill_response_example.model_dump_json()}"""


#######################################################################################################################################
@final
class SelectActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(TurnAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(TurnAction)

    #######################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        if len(self._react_entities_copy) == 0:
            return

        assert self._game.combat_system.is_on_going_phase
        await self._process_request(self._react_entities_copy)

    #######################################################################################################################################
    async def _process_request(self, react_entities: List[Entity]) -> None:

        # 处理角色规划请求
        request_handlers: List[ChatRequestHandler] = self._generate_requests(
            set(react_entities),
        )

        # 语言服务
        await self._game.langserve_system.gather(request_handlers=request_handlers)

        # 处理角色规划请求
        self._handle_responses(request_handlers)

    #######################################################################################################################################
    def _handle_responses(self, request_handlers: List[ChatRequestHandler]) -> None:

        for request_handler in request_handlers:

            if request_handler.response_content == "":
                logger.error(f"Agent: {request_handler._name}, Response is empty.")
                continue

            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._handle_response(entity2, request_handler)

    #######################################################################################################################################
    def _handle_response(
        self, entity2: Entity, request_handler: ChatRequestHandler
    ) -> None:

        try:

            format_response = SkillSelectionResponse.model_validate_json(
                format_string.json_format.strip_json_code_block(
                    request_handler.response_content
                )
            )

            logger.info(f"format_response 成功！ = {request_handler.response_content}")

            skill_candidate_comp = entity2.get(SkillCandidateQueueComponent)
            for skill in skill_candidate_comp.queue:

                if skill.name == format_response.skill:

                    # 给场景添加！！！
                    stage_entity = self._game.safe_get_stage_entity(entity2)
                    assert stage_entity is not None
                    if not stage_entity.has(StageDirectorAction):
                        stage_entity.replace(
                            StageDirectorAction,
                            stage_entity._name,
                            "",
                            "",
                        )

                    # 给角色添加！！！
                    assert not entity2.has(SelectAction)
                    entity2.replace(
                        SelectAction,
                        skill_candidate_comp.name,
                        format_response.targets,
                        skill,
                        format_response.interaction,
                        format_response.reason,
                    )
                    break
        except:
            logger.error(
                f"""返回格式错误: {entity2._name}, Response = \n{request_handler.response_content}"""
            )

    #######################################################################################################################################
    def _generate_requests(
        self, actor_entities: Set[Entity]
    ) -> List[ChatRequestHandler]:

        request_handlers: List[ChatRequestHandler] = []

        for entity in actor_entities:

            #
            current_stage = self._game.safe_get_stage_entity(entity)
            assert current_stage is not None

            #
            assert entity.has(SkillCandidateQueueComponent)
            message = _generate_prompt(
                current_stage._name,
                current_stage.get(StageEnvironmentComponent).narrate,
                entity.get(SkillCandidateQueueComponent).queue,
                entity.get(TurnAction).round_turns,
            )

            # 生成请求处理器
            request_handlers.append(
                ChatRequestHandler(
                    name=entity._name,
                    prompt=message,
                    chat_history=self._game.get_agent_short_term_memory(
                        entity
                    ).chat_history,
                )
            )

        return request_handlers

    #######################################################################################################################################
