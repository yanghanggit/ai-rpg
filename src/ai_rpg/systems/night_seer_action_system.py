from typing import final, Set, Dict
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
    SeerCheckAction,
    AppearanceComponent,
    NightActionReadyComponent,
    MindEvent,
    NightActionCompletedComponent,
    DeathComponent,
)
from ..chat_services.client import ChatClient
from ..utils import json_format
from ..utils.md_format import format_dict_as_markdown_list
from ..game.sdg_game import SDGGame


###############################################################################################################################################
def _generate_check_decision_prompt(target_options_mapping: Dict[str, str]) -> str:
    """创建预言家查看决策提示"""
    response_sample = SeerCheckDecisionResponse(
        target_name="目标玩家的名字",
        reasoning="你选择这个目标的详细推理过程，包括你对该玩家的行为分析、可疑程度评估等。",
    )

    return f"""# 指令！作为预言家，你需要选择今晚要查看身份的目标。

## 当前可选的查看目标:

{format_dict_as_markdown_list(target_options_mapping)}

## 决策建议

作为预言家，你应该考虑以下因素来选择查看目标：
1. **可疑行为**: 优先查看那些言行可疑、可能是狼人的玩家
2. **信息获取**: 选择查看那些能给你带来最大价值信息的玩家
3. **生存策略**: 考虑查看那些对你的生存威胁最大的玩家
4. **团队利益**: 选择查看能帮助好人阵营获胜的关键玩家
5. **逐步排除**: 从最可疑的玩家开始逐步排除

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
class SeerCheckDecisionResponse(BaseModel):
    target_name: str
    reasoning: str


###############################################################################################################################################
@final
class NightSeerActionSystem(ReactiveProcessor):

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
            and entity.has(SeerComponent)
            and not entity.has(NightActionCompletedComponent)
            and not entity.has(DeathComponent)
        )

    ###############################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """预言家夜晚行动的主要执行逻辑"""

        assert len(entities) == 1, "不可能有多个预言家同时行动"

        seer_entity = entities[0]

        alive_player_entities = self._game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    WitchComponent,
                    VillagerComponent,
                    HunterComponent,
                ],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        if len(alive_player_entities) == 0:
            logger.warning("当前没有存活的玩家，预言家无法进行查看")
            return

        # 执行预言家查看决策和行动
        await self._execute_seer_check_action(seer_entity, alive_player_entities)

        seer_entity.replace(
            NightActionCompletedComponent,
            seer_entity.name,
        )

    ###############################################################################################################################################
    async def _execute_seer_check_action(
        self, seer_entity: Entity, alive_player_entities: Set[Entity]
    ) -> None:
        """执行预言家查看决策和行动"""
        # 让预言家进行查看决策推理
        target_name = await self._get_seer_check_decision(
            seer_entity, alive_player_entities
        )

        if target_name:
            self._perform_seer_check(seer_entity, target_name)
        else:
            logger.warning("预言家没有选择查看目标")

    ###############################################################################################################################################
    async def _get_seer_check_decision(
        self, seer_entity: Entity, alive_player_entities: Set[Entity]
    ) -> str:
        """让预言家进行查看决策推理，返回目标名称"""
        # 创建可选目标的外貌映射
        target_options_mapping = self._create_target_options_mapping(
            alive_player_entities
        )

        # 创建决策请求
        prompt = _generate_check_decision_prompt(target_options_mapping)
        agent_short_term_memory = self._game.get_agent_chat_history(seer_entity)
        request_handler = ChatClient(
            name=seer_entity.name,
            prompt=prompt,
            chat_history=agent_short_term_memory.chat_history,
        )

        # 执行请求
        await ChatClient.gather_request_post(clients=[request_handler])

        # 处理响应
        target_name = self._process_check_decision_response(
            request_handler, alive_player_entities
        )
        if target_name:
            logger.info(f"预言家 {seer_entity.name} 决定查看: {target_name}")

        return target_name

    ###############################################################################################################################################
    def _create_target_options_mapping(
        self, alive_player_entities: Set[Entity]
    ) -> Dict[str, str]:
        """创建可选目标的外貌映射"""
        target_mapping = {}
        for entity in alive_player_entities:
            appearance_comp = entity.get(AppearanceComponent)
            if appearance_comp:
                target_mapping[entity.name] = appearance_comp.appearance
            else:
                target_mapping[entity.name] = "外貌未知"
        return target_mapping

    ###############################################################################################################################################
    def _process_check_decision_response(
        self, request_handler: ChatClient, alive_player_entities: Set[Entity]
    ) -> str:
        """处理预言家查看决策响应，返回目标名称"""
        try:

            response = SeerCheckDecisionResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.response_content)
            )

            # 验证目标是否有效
            if response.target_name not in [e.name for e in alive_player_entities]:
                logger.error(f"预言家选择的目标 {response.target_name} 不在可选列表中")
                return ""

            # 记录预言家的决策过程
            seer_entity = self._game.get_entity_by_name(request_handler.name)
            if seer_entity:

                self._game.notify_entities(
                    set({seer_entity}),
                    MindEvent(
                        message=f"经过你的思考之后，你决定今晚要查看 {response.target_name} 的身份，理由是：{response.reasoning}",
                        actor=seer_entity.name,
                        content=f"经过你的思考之后，你决定今晚要查看 {response.target_name} 的身份，理由是：{response.reasoning}",
                    ),
                )

            return response.target_name

        except Exception as e:
            logger.error(f"处理预言家 {request_handler.name} 的决策响应时出现异常: {e}")
            logger.error(f"原始响应内容: {request_handler.response_content}")
            return ""

    ###############################################################################################################################################
    def _perform_seer_check(self, seer_entity: Entity, target_name: str) -> None:
        """执行具体的预言家查看行动"""
        target_entity = self._game.get_entity_by_name(target_name)

        if target_entity is not None:
            # 添加查看动作
            target_entity.replace(
                SeerCheckAction,
                target_entity.name,
                seer_entity.name,
            )

    ###############################################################################################################################################
