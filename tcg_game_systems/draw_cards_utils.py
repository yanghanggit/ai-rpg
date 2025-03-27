from pydantic import BaseModel
from entitas import Entity  # type: ignore
from extended_systems.chat_request_handler import ChatRequestHandler
import format_string.json_format
from components.components_v_0_0_1 import (
    StageEnvironmentComponent,
    HandComponent,
    HeroComponent,
    MonsterComponent,
)
from typing import List, Set, final
from loguru import logger
from models.v_0_0_1 import Skill
from game.tcg_game import TCGGame


#######################################################################################################################################
@final
class DrawCardResponse(BaseModel):
    attack: Skill
    defense: Skill
    support: Skill


#######################################################################################################################################
def _generate_prompt(
    current_stage: str,
    current_stage_narration: str,
) -> str:

    default_response_example = DrawCardResponse(
        attack=Skill(
            name="攻击技能",
            description="攻击技能描述",
            effect="攻击技能效果",
        ),
        defense=Skill(
            name="防御技能",
            description="防御技能描述",
            effect="防御技能效果",
        ),
        support=Skill(
            name="支援技能",
            description="支援技能描述",
            effect="支援技能效果",
        ),
    )

    return f"""# 请根据你的能力情况，生成你的技能
## 当前场景
{current_stage}
### 场景描述
{current_stage_narration}
## 注意事项
如生成的技能跟属性有关(依赖/增加/减少)，需在技能描述与影响里明确说明。
## 输出要求
- 不要使用```json```来封装内容。
### 输出格式(JSON)
{default_response_example.model_dump_json()}"""


#######################################################################################################################################
@final
class DrawCardsUtils:

    def __init__(self, game_context: TCGGame, actor_entities: Set[Entity]) -> None:
        self._game: TCGGame = game_context
        self._actor_entities: Set[Entity] = actor_entities

        for entity in self._actor_entities:
            assert entity.has(HeroComponent) or entity.has(
                MonsterComponent
            ), f"{entity._name} must have HeroComponent or MonsterComponent"

    #######################################################################################################################################
    async def draw_cards(self) -> None:
        if len(self._actor_entities) == 0:
            return

        # 先清除
        self._clear(self._actor_entities)

        # 处理请求
        await self._process_chat_requests(self._actor_entities)

    #######################################################################################################################################
    def _clear(self, actor_entities: Set[Entity]) -> None:
        copy_actor_entities = actor_entities.copy()
        for entity in copy_actor_entities:
            if entity.has(HandComponent):
                entity.remove(HandComponent)

    #######################################################################################################################################
    async def _process_chat_requests(self, react_entities: Set[Entity]) -> None:

        # 处理角色规划请求
        request_handlers: List[ChatRequestHandler] = self._generate_requests(
            react_entities
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

            format_response = DrawCardResponse.model_validate_json(
                format_string.json_format.strip_json_code_block(
                    request_handler.response_content
                )
            )

            # 设置3个技能
            entity2.replace(
                HandComponent,
                entity2._name,
                [
                    format_response.attack,
                    format_response.defense,
                    format_response.support,
                ],
            )

        except:
            logger.error(
                f"""返回格式错误: {entity2._name}, Response = \n{request_handler.response_content}"""
            )

    #######################################################################################################################################
    def _generate_requests(
        self, actor_entities: set[Entity]
    ) -> List[ChatRequestHandler]:

        request_handlers: List[ChatRequestHandler] = []

        for entity in actor_entities:

            #
            current_stage = self._game.safe_get_stage_entity(entity)
            assert current_stage is not None

            # 生成消息
            message = _generate_prompt(
                current_stage._name,
                current_stage.get(StageEnvironmentComponent).narrate,
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
