from typing import final, Set, Dict
from overrides import override
from pydantic import BaseModel
from ..entitas import ExecuteProcessor, Matcher, Entity
from ..game.tcg_game import TCGGame
from loguru import logger
from ..models import (
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    DeathComponent,
    SeerCheckAction,
    AppearanceComponent,
    WolfKillAction,
)
from ..chat_services.client import ChatClient
from ..utils import json_format
from ..utils.md_format import format_dict_as_markdown_list


###############################################################################################################################################
@final
class SeerCheckDecisionResponse(BaseModel):
    target_name: str
    reasoning: str


###############################################################################################################################################
@final
class SocialDeductionSeerSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        """预言家夜晚行动的主要执行逻辑"""
        assert self._game._time_marker % 2 == 1, "时间标记必须是奇数，是夜晚"
        logger.info(f"夜晚 {self._game._time_marker // 2 + 1} 开始")
        logger.info("预言家请睁眼，选择你要查看的玩家")

        seer_entity = self._get_seer()
        if not seer_entity:
            return

        alive_player_entities = self._get_alive_players()
        if not alive_player_entities:
            return

        # 执行预言家查看决策和行动
        await self._execute_seer_check_action(seer_entity, alive_player_entities)

    ###############################################################################################################################################
    def _get_seer(self) -> Entity | None:
        """获取存活的预言家实体"""
        alive_seer_entities = self._game.get_group(
            Matcher(
                all_of=[SeerComponent],
            )
        ).entities.copy()

        if len(alive_seer_entities) == 0:
            logger.warning("当前没有存活的预言家，无法进行查看")
            return None

        assert len(alive_seer_entities) == 1, "预言家不可能有多个"
        seer_entity = next(iter(alive_seer_entities))
        logger.debug(f"当前预言家实体 = {seer_entity.name}")

        if (
            self._game._time_marker == 1
            and seer_entity.has(WolfKillAction)
            and seer_entity.has(DeathComponent)
        ):
            logger.warning(
                f"预言家 {seer_entity.name} 走到这里说明是第一夜预言家被狼人杀害了，所以算作可以行动的预言家"
            )
            return seer_entity

        if seer_entity.has(DeathComponent):
            logger.warning(
                f"预言家 {seer_entity.name} 已经彻底死亡，无法进行预言家行动"
            )
            return None

        return seer_entity

    ###############################################################################################################################################
    def _get_alive_players(self) -> Set[Entity]:
        """获取所有存活的玩家实体（排除预言家自己）"""
        alive_player_entities = self._game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        if len(alive_player_entities) == 0:
            logger.warning("当前没有存活的玩家，无法进行查看")
            return set()

        logger.debug(f"当前存活的玩家实体 = {[e.name for e in alive_player_entities]}")
        return alive_player_entities

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
            await self._perform_seer_check(seer_entity, target_name)
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
        prompt = self._create_check_decision_prompt(target_options_mapping)
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
    def _create_check_decision_prompt(
        self, target_options_mapping: Dict[str, str]
    ) -> str:
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

## 输出格式

### 标准示例

```json
{response_sample.model_dump_json()}
```

## 输出要求

请严格按照上述的 JSON 标准示例 格式输出！你必须从上述可选目标中选择一个作为target_name。"""

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
                self._game.append_human_message(
                    seer_entity,
                    f"# 发生事件，经过你的思考之后，你决定今晚要查看 {response.target_name} 的身份，理由是：{response.reasoning}",
                )

            return response.target_name

        except Exception as e:
            logger.error(f"处理预言家 {request_handler.name} 的决策响应时出现异常: {e}")
            logger.error(f"原始响应内容: {request_handler.response_content}")
            return ""

    ###############################################################################################################################################
    async def _perform_seer_check(self, seer_entity: Entity, target_name: str) -> None:
        """执行具体的预言家查看行动"""
        target_entity = self._game.get_entity_by_name(target_name)

        if target_entity is not None:
            # 添加查看动作
            target_entity.replace(
                SeerCheckAction,
                target_entity.name,
                seer_entity.name,
            )

            logger.info(f"预言家查看了玩家 {target_entity.name}")

            # 揭示查看结果
            if target_entity.has(WerewolfComponent):
                logger.info(f"预言家查看的玩家 {target_entity.name} 是 狼人")
                self._game.append_human_message(
                    seer_entity,
                    f"# 提示！你查看了玩家 {target_entity.name} 的身份，结论：{target_entity.name} 是 狼人！",
                )
            else:
                logger.info(f"预言家查看的玩家 {target_entity.name} 不是 狼人")
                self._game.append_human_message(
                    seer_entity,
                    f"# 提示！你查看了玩家 {target_entity.name} 的身份，结论：{target_entity.name} 不是 狼人。",
                )
        else:
            logger.error(f"找不到目标实体: {target_name}")

    ###############################################################################################################################################
