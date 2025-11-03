import random
from typing import final, List, Dict, Tuple
from overrides import override
from pydantic import BaseModel
from ..entitas import Matcher, Entity, GroupEvent, ReactiveProcessor
from loguru import logger
from ..models import (
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    HunterComponent,
    DeathComponent,
    AppearanceComponent,
    NightActionReadyComponent,
    NightKillTargetComponent,
    MindEvent,
    NightActionCompletedComponent,
)
from ..chat_services.client import ChatClient
from ..utils import json_format
from ..utils.md_format import format_dict_as_markdown_list
from ..game.sdg_game import SDGGame


###############################################################################################################################################
def _generate_prompt(target_options_mapping: Dict[str, str]) -> str:
    """创建狼人击杀决策提示"""
    response_sample = WerewolfKillDecisionResponse(
        target_name="目标玩家的名字",
        reasoning="你选择这个目标的详细推理过程，包括对该玩家身份的分析、威胁评估等。",
    )

    return f"""# 指令！作为狼人，你需要选择今晚要击杀的目标。

## 当前可选的击杀目标:

{format_dict_as_markdown_list(target_options_mapping)}

## 决策建议

作为狼人，你应该考虑以下因素来选择击杀目标：
1. **身份威胁**: 优先击杀可能的预言家、女巫等特殊身份
2. **推理能力**: 击杀那些逻辑清晰、容易识破狼人的玩家  
3. **影响力**: 击杀那些在讨论中有话语权、能影响其他玩家的人
4. **隐蔽性**: 避免选择那些可能暴露你身份的目标
5. **团队配合**: 考虑与其他狼人同伴的策略配合

## 注意，严格遵循推理机制

## 输出格式

### 标准示例

```json
{response_sample.model_dump_json()}
```

## 输出要求

请严格按照上述的 JSON 标准示例 格式输出！你必须从上述可选目标中选择一个作为target_name。"""


###############################################################################################################################################
@final
class WerewolfKillDecisionResponse(BaseModel):
    target_name: str
    reasoning: str


###############################################################################################################################################
@final
class NightWerewolfActionSystem(ReactiveProcessor):

    def __init__(self, game_context: SDGGame) -> None:
        super().__init__(game_context)
        self._game: SDGGame = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(NightActionReadyComponent): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(NightActionReadyComponent)
            and entity.has(WerewolfComponent)
            and not entity.has(NightActionCompletedComponent)
            and not entity.has(DeathComponent)
        )

    ###############################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """狼人夜晚行动的主要执行逻辑"""
        assert len(entities) > 0, "触发实体列表不能为空"

        logger.debug("狼人行动阶段！！！！！！！！")

        # 获取所有存活的好人
        alive_town_entities = self._game.get_group(
            Matcher(
                any_of=[
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                    HunterComponent,
                ],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        if len(alive_town_entities) == 0:
            logger.debug("没有存活的好人，狼人无法进行击杀")
            return

        # 创建可选目标的外貌映射
        target_mapping = {}
        for entity in alive_town_entities:
            appearance_comp = entity.get(AppearanceComponent)
            if appearance_comp:
                target_mapping[entity.name] = appearance_comp.appearance
            else:
                target_mapping[entity.name] = "外貌未知"

        # 生成提示词
        prompt = _generate_prompt(target_mapping)

        # 创建请求处理器
        request_handlers: List[ChatClient] = []
        for entity in entities:
            agent_memory = self._game.get_agent_chat_history(entity)
            request_handlers.append(
                ChatClient(
                    name=entity.name,
                    prompt=prompt,
                    chat_history=agent_memory.chat_history,
                )
            )

        # 并发执行所有请求
        await ChatClient.gather_request_post(clients=request_handlers)

        # 处理所有响应, 收集格式化后的响应
        format_responses: List[Tuple[Entity, Entity, str]] = []
        for request_handler in request_handlers:

            try:

                format_response = WerewolfKillDecisionResponse.model_validate_json(
                    json_format.strip_json_code_block(request_handler.response_content)
                )

                werewolf_entity = self._game.get_entity_by_name(request_handler.name)
                assert werewolf_entity is not None, "找不到狼人实体"

                target_entity = self._game.get_entity_by_name(
                    format_response.target_name
                )

                if target_entity is None:
                    logger.error(f"找不到目标实体: {format_response.target_name}")
                    continue

                format_responses.append(
                    (werewolf_entity, target_entity, format_response.reasoning)
                )

            except Exception as e:
                logger.error(
                    f"处理狼人 {request_handler.name} 的决策响应时出现异常: {e}"
                )

        if len(format_responses) == 0:
            logger.error("没有有效的狼人击杀决策响应，无法进行击杀")
            return

        # 随机选择一个响应作为最终决定
        chosen_response = random.choice(format_responses)

        # 目标直接做击杀标记, 最终决定！
        chosen_response[1].replace(
            NightKillTargetComponent,
            chosen_response[1].name,
            self._game._turn_counter,
        )
        logger.debug(
            f"狼人杀人{chosen_response[0].name} 行动完成，玩家 {chosen_response[1].name} 被标记为死亡, 击杀时间标记 {self._game._turn_counter}"
        )

        # 自身的添加上下文。
        self._game.notify_entities(
            set({chosen_response[0]}),
            MindEvent(
                message=f"经过你的思考之后，你决定今晚要击杀 {chosen_response[1].name}，理由是：{chosen_response[2]}",
                actor=chosen_response[0].name,
                content=f"经过你的思考之后，你决定今晚要击杀 {chosen_response[1].name}，理由是：{chosen_response[2]}",
            ),
        )

        # 标记夜晚行动完成
        chosen_response[0].replace(
            NightActionCompletedComponent, chosen_response[0].name
        )

        # 通知所有活着的狼人最终决定
        for other_response in format_responses:

            if other_response == chosen_response:
                continue

            self._game.notify_entities(
                set({other_response[0]}),
                MindEvent(
                    message=f"经过你的思考之后，你决定今晚要击杀 {other_response[1].name}，理由是：{other_response[2]} 经过团队商议，最终采纳了 {chosen_response[0].name} 的建议，决定击杀 {chosen_response[1].name}。",
                    actor=other_response[0].name,
                    content=f"经过你的思考之后，你决定今晚要击杀 {other_response[1].name}，理由是：{other_response[2]} 经过团队商议，最终采纳了 {chosen_response[0].name} 的建议，决定击杀 {chosen_response[1].name}。",
                ),
            )

            # 标记夜晚完成。
            other_response[0].replace(
                NightActionCompletedComponent, other_response[0].name
            )

    ###############################################################################################################################################
