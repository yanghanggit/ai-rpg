import random
from pydantic import BaseModel
from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from agent.chat_request_handler import ChatRequestHandler
import format_string.json_format
from components.components import (
    StageEnvironmentComponent,
    ActorComponent,
    SkillCandidateQueueComponent,
)
from overrides import override
from typing import List, final
from game.tcg_game import TCGGame
from loguru import logger
from tcg_models.v_0_0_1 import Skill
from components.actions2 import SkillAction2


#######################################################################################################################################
@final
class SelectSkillResponse(BaseModel):
    skill: str
    reason: str


#######################################################################################################################################
def _generate_battle_prompt(
    current_stage: str,
    current_stage_narration: str,
    # current_story: str,
    skill_candidates: List[Skill],
    action_order: List[str],
) -> str:

    skill_candidates1 = [skill.model_dump_json() for skill in skill_candidates]

    select_skill_response_example = SelectSkillResponse(
        skill="技能名称",
        reason="技能使用原因",
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
### 输出格式(JSON)
{select_skill_response_example.model_dump_json()}"""


#######################################################################################################################################
@final
class ExecuteSkillSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:
        await self._process_actor_planning_request()

    #######################################################################################################################################
    async def _process_actor_planning_request(self) -> None:

        # 获取所有需要进行角色规划的角色
        actor_entities = self._game.get_group(
            Matcher(
                all_of=[
                    SkillAction2,
                ],
            )
        ).entities

        # 生成消息
        # self._round_action_order = [action._name for action in self._action_order()]
        assert len(self._game._round_action_order) > 0

        # 处理角色规划请求
        # request_handlers: List[ChatRequestHandler] = self._generate_chat_requests(
        #     actor_entities, self._round_action_order
        # )

        # # 语言服务
        # await self._game.langserve_system.gather(request_handlers=request_handlers)

        # # 处理角色规划请求
        # self._handle_chat_responses(request_handlers)

    #######################################################################################################################################
    def _handle_chat_responses(
        self, request_handlers: List[ChatRequestHandler]
    ) -> None:

        for request_handler in request_handlers:

            if request_handler.response_content == "":
                logger.error(f"Agent: {request_handler._name}, Response is empty.")
                continue

            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._handle_actor_response(entity2, request_handler)

    #######################################################################################################################################
    def _handle_actor_response(
        self, entity2: Entity, request_handler: ChatRequestHandler
    ) -> None:

        try:

            # pass
            format_response = SelectSkillResponse.model_validate_json(
                format_string.json_format.strip_json_code_block(
                    request_handler.response_content
                )
            )

            #
            skill_candidate_comp = entity2.get(SkillCandidateQueueComponent)
            for skill in skill_candidate_comp.queue:
                if skill.name == format_response.skill:
                    entity2.replace(SkillAction2, skill_candidate_comp.name, skill)
                    break
        except:
            logger.error(
                f"""返回格式错误: {entity2._name}, Response = \n{request_handler.response_content}"""
            )

    #######################################################################################################################################
    def _generate_chat_requests(
        self, actor_entities: set[Entity], action_order: List[str]
    ) -> List[ChatRequestHandler]:

        request_handlers: List[ChatRequestHandler] = []

        for entity in actor_entities:

            #
            current_stage = self._game.safe_get_stage_entity(entity)
            assert current_stage is not None

            #
            assert entity.has(SkillCandidateQueueComponent)
            message = _generate_battle_prompt(
                current_stage._name,
                current_stage.get(StageEnvironmentComponent).narrate,
                # current_stage.get(StageEnvironmentComponent).story,
                entity.get(SkillCandidateQueueComponent).queue,
                action_order,
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
    # def _action_order(self) -> List[Entity]:
    #     # 获取所有需要进行角色规划的角色
    #     actor_entities = self._game.get_group(
    #         Matcher(
    #             all_of=[
    #                 ActorComponent,
    #             ],
    #         )
    #     ).entities.copy()

    #     actor_entities1 = list(actor_entities)
    #     random.shuffle(actor_entities1)
    #     return actor_entities1

    #######################################################################################################################################
