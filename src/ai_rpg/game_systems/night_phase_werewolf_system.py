from typing import final, List, Set, Dict, Tuple
from overrides import override
from pydantic import BaseModel
from ..entitas import Matcher, Entity, GroupEvent, ReactiveProcessor
from loguru import logger
from ..models import (
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    DeathComponent,
    WolfKillAction,
    AppearanceComponent,
    NightTurnActionComponent,
    MindVoiceAction,
    NightKillMarkerComponent,
)
from ..chat_services.client import ChatClient
from ..utils import json_format
from ..utils.md_format import format_dict_as_markdown_list
import random

# from .base_action_reactive_system import BaseActionReactiveSystem
from ..game.tcg_game import TCGGame


###############################################################################################################################################
def _generate_kill_decision_prompt(target_options_mapping: Dict[str, str]) -> str:
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
class NightPhaseWerewolfSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(NightTurnActionComponent): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(NightTurnActionComponent) and entity.has(WerewolfComponent)

    #######################################################################################################################################

    ###############################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """狼人夜晚行动的主要执行逻辑"""
        assert len(entities) > 0, "触发实体列表不能为空"
        if len(entities) == 0:
            return

        # assert (
        #     self._game._werewolf_game_turn_counter % 2 == 1
        # ), "时间标记必须是奇数，是夜晚"
        # logger.debug(f"夜晚 {self._game._werewolf_game_turn_counter // 2 + 1} 开始")
        logger.debug("狼人行动阶段！！！！！！！！")

        # 获取所有存活的好人
        alive_town_entities = self._game.get_group(
            Matcher(
                any_of=[
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        if not alive_town_entities:
            return

        # 执行狼人击杀决策和行动
        await self._execute_werewolf_kill_action(entities, alive_town_entities)

    ###############################################################################################################################################
    async def _execute_werewolf_kill_action(
        self, werewolf_entities: List[Entity], alive_town_entities: Set[Entity]
    ) -> None:
        """执行狼人击杀决策和行动"""
        # 让每个狼人进行击杀决策推理
        target_recommendations = await self._get_werewolf_kill_decisions(
            werewolf_entities, alive_town_entities
        )

        if target_recommendations:
            chosen_target, recommender = random.choice(target_recommendations)
            await self._perform_kill_action(
                chosen_target, recommender, werewolf_entities
            )
        else:
            logger.warning("狼人没有推荐任何击杀目标")

    ###############################################################################################################################################
    def _notify_werewolves_kill_decision(
        self,
        werewolf_entities: List[Entity],
        chosen_target_name: str,
        recommender_name: str,
    ) -> None:
        """通知所有狼人最终的击杀决定"""
        logger.info(
            f"最终的事件通知: 采取狼人 {recommender_name} 击杀的击杀目标 => {chosen_target_name}"
        )
        for werewolf in werewolf_entities:
            # self._game.append_human_message(
            #     werewolf,
            #     f"# 发生事件！经过团队商议，最终采纳了 {recommender_name} 的建议，决定击杀 {chosen_target_name}。",
            # )

            mind_voice_action = werewolf.get(MindVoiceAction)
            if mind_voice_action:
                mind_voice_message = str(mind_voice_action.message)
            else:
                mind_voice_message = ""

            werewolf.replace(
                MindVoiceAction,
                werewolf.name,
                f"{mind_voice_message}\n经过团队商议，最终采纳了 {recommender_name} 的建议，决定击杀 {chosen_target_name}。",
            )

    ###############################################################################################################################################
    async def _perform_kill_action(
        self,
        chosen_target_name: str,
        recommender_name: str,
        werewolf_entities: List[Entity],
    ) -> None:
        """执行具体的击杀行动"""
        target_entity = self._game.get_entity_by_name(chosen_target_name)
        if target_entity is None:
            logger.error(f"找不到目标实体: {chosen_target_name}")
            return

        # 添加击杀动作和死亡状态
        target_entity.replace(
            WolfKillAction,
            target_entity.name,
            recommender_name,
            f"根据 {recommender_name} 的建议，狼人团队决定击杀 {chosen_target_name}",
        )

        # 注意！！！！添加标记，方便女巫的规划时可以进行参考，也防止女巫与狼人不在一个pass下的执行，aciton被清除的问题。
        logger.debug(
            f"狼人杀人行动完成，玩家 {target_entity.name} 被标记为死亡, 击杀时间标记 {self._game._werewolf_game_turn_counter}"
        )
        target_entity.replace(
            NightKillMarkerComponent,
            target_entity.name,
            self._game._werewolf_game_turn_counter,
        )

        # 通知所有活着的狼人最终决定
        self._notify_werewolves_kill_decision(
            werewolf_entities, chosen_target_name, recommender_name
        )

    ###############################################################################################################################################
    async def _get_werewolf_kill_decisions(
        self, werewolf_entities: List[Entity], alive_town_entities: Set[Entity]
    ) -> List[Tuple[str, str]]:
        """让每个狼人进行击杀决策推理，返回推荐的目标名称和发起者的元组列表"""

        # 创建可选目标的外貌映射
        target_options_mapping = self._create_target_options_mapping(
            alive_town_entities
        )

        # 为每个狼人创建决策请求
        request_handlers = self._create_kill_decision_requests(
            werewolf_entities, target_options_mapping
        )

        # 并发执行所有请求
        await ChatClient.gather_request_post(clients=request_handlers)

        # 处理响应并收集推荐目标
        target_recommendations: List[Tuple[str, str]] = []
        for request_handler in request_handlers:
            target_recommendations.append(
                self._process_kill_decision_response(request_handler)
            )

        return target_recommendations

    ###############################################################################################################################################
    def _create_target_options_mapping(
        self, alive_town_entities: Set[Entity]
    ) -> Dict[str, str]:
        """创建可选目标的外貌映射"""
        target_mapping = {}
        for entity in alive_town_entities:
            appearance_comp = entity.get(AppearanceComponent)
            if appearance_comp:
                target_mapping[entity.name] = appearance_comp.appearance
            else:
                target_mapping[entity.name] = "外貌未知"
        return target_mapping

    ###############################################################################################################################################
    def _create_kill_decision_requests(
        self,
        werewolf_entities: List[Entity],
        target_options_mapping: Dict[str, str],
    ) -> List[ChatClient]:
        """为所有狼人创建击杀决策请求"""
        request_handlers: List[ChatClient] = []
        prompt = _generate_kill_decision_prompt(target_options_mapping)

        for entity in werewolf_entities:
            agent_short_term_memory = self._game.get_agent_chat_history(entity)
            request_handlers.append(
                ChatClient(
                    name=entity.name,
                    prompt=prompt,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )

        return request_handlers

    ###############################################################################################################################################
    def _process_kill_decision_response(
        self, request_handler: ChatClient
    ) -> Tuple[str, str]:
        """处理狼人击杀决策响应，返回推荐的目标名称和推理过程"""
        try:
            response = WerewolfKillDecisionResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.response_content)
            )

            werewolf_entity = self._game.get_entity_by_name(request_handler.name)
            assert werewolf_entity is not None, "找不到狼人实体"

            # self._game.append_human_message(
            #     werewolf_entity,
            #     f"# 发生事件，经过你的思考之后，你决定今晚要击杀 {response.target_name}，理由是：{response.reasoning}",
            # )

            werewolf_entity.replace(
                MindVoiceAction,
                werewolf_entity.name,
                f"经过你的思考之后，你决定今晚要击杀 {response.target_name}，理由是：{response.reasoning}",
            )

            return response.target_name, werewolf_entity.name

        except Exception as e:
            logger.error(f"处理狼人 {request_handler.name} 的决策响应时出现异常: {e}")
            logger.error(f"原始响应内容: {request_handler.response_content}")

        return "", ""

    ###############################################################################################################################################
