from entitas import Entity, Matcher, GroupEvent  # type: ignore
from components.actions import CardAction, RemoveTagAction, AddTagAction
from typing import final, override, Optional, Set, List
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from loguru import logger
from components.components import WorldSystemComponent, TagsComponent, ActorComponent
from agent.chat_request_handler import ChatRequestHandler
from tcg_models.v_0_0_1 import CardObject
import copy
import random

"""
目前只测试出牌的逻辑。达到 冲锋/上挑/重击 能够推理的基本符合逻辑。


# 核心规则： 
- 行动者的行动会以卡牌的形式进行。
- 如果一次行动中有多张卡牌，那么卡牌的执行顺序是按照给出的顺序执行的。每一张卡牌的动作都会影响下一张，卡牌的执行，注意看TAG的内容，变化与依赖关系。
- 不要提前做出任何假设(例如假设角色已经有某些TAG)，只根据给出的信息进行推理，推理出来的TAG会影响后续的卡牌执行。
- 必须充分考虑所有TAG的影响，包括使用者角色的TAG、目标的TAG和场景的TAG。
- 必须充分考虑卡牌对友方造成影响的可能性。
- 发挥天马行空的想象，给出富有戏剧性的结果，但必须基于逻辑和TAG的相互作用。
# 角色信息：
{"\n".join(user_tags)}
## 团结度
- 15
### 目标：
- 角色.怪物.强壮哥布林
# 场景信息：
## 场景.洞穴：
- <恶臭>： 对象恶臭熏天，令人难以忍受。
# 卡牌的信息如下：
{"\n".join(card_prompt_list)}

## 卡牌的执行顺序如下:
{"\n".join(card_names)}
# 输出内容：
## 输出内容1:
判断每张牌的对应动作对目标的有效性，返回范围为[1，5]的整数评分，数字越大代表有效性越高。1代表效果很差，3代表效果一般，5代表效果极佳。误伤友军不会影响评分。最后给出所有评分之和。
## 输出内容2：
给出场景和所有角色最终需要添加的和移除的TAG。
## 输出内容3：
给出最终描述。
## 输出内容4：
给出详细的思考过程，重点说明TAG的相互作用。

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
        # for entity in self._react_entities_copy:
        #     await self._handle_card_action(entity)
        if len(self._react_entities_copy) > 0:
            await self._handle_card_action(self._react_entities_copy)

    ####################################################################################################################################
    async def _handle_card_action(self, entities: List[Entity]) -> None:

        world_system_entity = self._get_world_system()
        assert world_system_entity is not None

        card_pool = []
        for entity in entities:
            card_pool.extend(self._game.get_card_pool(entity=entity))

        # 测试
        shuffled_player_cards = copy.copy(card_pool)
        random.shuffle(shuffled_player_cards)

        request_handlers: List[ChatRequestHandler] = []

        gen_prompt = self._gen_prompt(
            entities=entities, player_cards=shuffled_player_cards
        )

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

        return f"""{card_object.name}:
- 使用者：{card_object.owner}
- 描述：{card_object.description}
- 隐藏信息：{card_object.insight}"""

    ####################################################################################################################################
    def _gen_prompt(
        self, entities: List[Entity], player_cards: List[CardObject]
    ) -> str:

        #
        card_prompt_list = []
        for card_object in player_cards:
            card_prompt = self._gen_card_prompt(card_object=card_object)
            card_prompt_list.append(card_prompt)

        #
        card_names_with_index = []
        for index, card_object in enumerate(player_cards):
            card_names_with_index.append(f"{index + 1}. {card_object.name}")

        #
        # user_tags = []
        # for entity in entities:
        #     user_tags.append("" + entity.get(ActorComponent).name + ":")
        #     for taginfo in entity.get(TagsComponent).tags:
        #         user_tags.append("- " + taginfo.name + ": " + taginfo.description)

        #

        return f"""# 玩家团队将执行一次行动。
    
## 核心规则： 
- 行动者的行动会以卡牌的形式进行。
- 如果一次行动中有多张卡牌，那么卡牌的执行顺序是按照给出的顺序执行的。每一张卡牌的动作都会影响下一张，卡牌的执行，注意看变化与依赖关系。
- 不要提前做出任何假设，只根据给出的信息进行推理，推理出来的结果会影响后续的卡牌执行。
- 发挥天马行空的想象，给出富有戏剧性的结果。

## 目标：
- 角色.怪物.强壮哥布林

## 场景信息：
- 场景.洞穴：对象恶臭熏天，令人难以忍受。

## 卡牌的信息如下：
{"\n".join(card_prompt_list)}

## 卡牌的执行顺序如下:
{"\n".join(card_names_with_index)}

## 输出内容：
- 给出最终描述。
- 给出详细的思考过程。"""

    ####################################################################################################################################
