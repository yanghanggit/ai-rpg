from entitas import Entity, Matcher, GroupEvent  # type: ignore
from components.actions import (
    CardAction,
)
from typing import final, override, Optional, Set, List
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from loguru import logger
from components.components import WorldSystemComponent
from agent.chat_request_handler import ChatRequestHandler
from tcg_models.v_0_0_1 import CardObject
import copy
import random

"""
目前只测试出牌的逻辑。达到 冲锋/上挑/重击 能够推理的基本符合逻辑。
"""


#######################################################################################################################################
@final
class CardActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(CardAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(CardAction)

    ####################################################################################################################################
    async def a_execute2(self) -> None:
        for entity in self._react_entities_copy:
            await self._handle_card_action(entity)

    ####################################################################################################################################
    async def _handle_card_action(self, entity: Entity) -> None:

        world_system_entity = self._get_world_system()
        assert world_system_entity is not None

        card_pool = self._game.get_card_pool(entity=entity)

        # 测试
        shuffled_player_cards = copy.copy(card_pool)
        random.shuffle(shuffled_player_cards)

        request_handlers: List[ChatRequestHandler] = []

        gen_prompt = self._gen_prompt(entity=entity, player_cards=shuffled_player_cards)

        agent_short_term_memory = self._game.get_agent_short_term_memory(
            world_system_entity
        )
        request_handlers.append(
            ChatRequestHandler(
                name=world_system_entity._name,
                prompt=gen_prompt,
                chat_history=agent_short_term_memory.chat_history,
            )
        )

        # 并发
        await self._game.langserve_system.gather(request_handlers=request_handlers)

        # 添加上下文。
        for request_handler in request_handlers:

            if request_handler.response_content == "":
                logger.error(f"Agent: {request_handler._name}, Response is empty.")
                continue

            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            entity2 = self._context.get_entity_by_name(request_handler._name)
            assert entity2 is not None

            logger.debug(f"{request_handler._prompt}")
            logger.debug(f"{request_handler.response_content}")

    ####################################################################################################################################
    def _get_world_system(self) -> Optional[Entity]:

        entities: Set[Entity] = self._context.get_group(
            Matcher(
                any_of=[WorldSystemComponent],
            )
        ).entities

        if len(entities) > 0:
            return next(iter(entities))

        return None

    ####################################################################################################################################
    def _gen_card_prompt(self, card_object: CardObject) -> str:

        return f"""{card_object.name}
- 描述与效果：{card_object.description}
- 隐藏信息：{card_object.insight}"""

    ####################################################################################################################################
    def _gen_prompt(self, entity: Entity, player_cards: List[CardObject]) -> str:

        #
        card_prompt_list = []
        for card_object in player_cards:
            card_prompt = self._gen_card_prompt(card_object=card_object)
            card_prompt_list.append(card_prompt)

        #
        card_names = []
        for index, card_object in enumerate(player_cards):
            card_names.append(f"第{index + 1}步:{card_object.name}")

        return f"""# 行动者：{entity._name} 将要执行卡牌的动作，请你做出推理与演绎。
    
## 核心规则： 
- 行动者的行动会以卡牌的形式进行。
- 卡牌会有对应的描述与意图效果 与 隐藏信息。
- 如果一次行动中有多张卡牌，那么卡牌的执行顺序是按照给出的顺序执行的。每一张卡牌的动作都会影响下一张，卡牌的执行，注意看TAG的内容，变化与依赖关系。
- 不要提前做出任何假设(例如假设角色已经有某些TAG)，只根据给出的信息进行推理，推理出来的TAG会影响后续的卡牌执行。
    
## 卡牌的信息：
{"\n".join(card_prompt_list)}

## 卡牌的执行顺序如下:
{"\n".join(card_names)}

## 输出内容：
- 判断每张牌的对应动作是否能成功。
- 请给出思考过程。"""

    ####################################################################################################################################
