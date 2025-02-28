from entitas import Entity, Matcher, GroupEvent  # type: ignore
from components.actions import (
    CardAction,
    RemoveTagAction,
    AddTagAction
)
from typing import final, override, Optional, Set, List
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from loguru import logger
from components.components import WorldSystemComponent, TagsComponent
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
- 描述：{card_object.description}
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
            card_names.append(f"{index + 1}. {card_object.name}")

        #
        user_tags = list(entity.get(TagsComponent).tags).copy()

        #
        stage_tags = list(self._context.safe_get_stage_entity(entity).get(TagsComponent).tags).copy()

        return f"""#行动者： {entity._name} 
## 行动者所持TAG：
{"\n".join(user_tags)}
# 目标： 角色.怪物.强壮哥布林
## 目标所持TAG：
<强壮>,<哥布林>
# 场景： 场景.洞穴
## 场景所持TAG：
{"\n".join(stage_tags)}
# 卡牌的信息如下：
{"\n".join(card_prompt_list)}
## 卡牌的执行顺序如下:
{"\n".join(card_names)}
# 输出内容：
## 输出内容1:
判断每张牌的对应动作是否能成功。
## 输出内容2：
给出每个角色最终需要添加的和移除的TAG。
## 输出内容3：
给出思考过程。
# 注意：
- 严格遵循TAG间的依赖关系。
- 严格遵循执行顺序，卡牌的动作是严格按照1、2、3顺序执行的。
- 先一步的动作结果将影响下一步动作的执行。
- 进行合理性推测时，仅能以TAG为推理依据。
- 尽可能考虑所有TAG带来的潜在影响。
- 不要假设任何未于TAG上体现的前提。"""

    ####################################################################################################################################
