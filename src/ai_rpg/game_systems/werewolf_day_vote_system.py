from typing import final, List
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..entitas import ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    DeathComponent,
    DayDiscussionFlagComponent,
    MindVoiceAction,
    NightKillFlagComponent,
    VoteAction,
    MindVoiceAction,
)
from ..chat_services.client import ChatClient
from ..utils import json_format


###############################################################################################################################################
@final
class DayVoteResponse(BaseModel):
    mind_voice: str
    target_name: str


@final
class WerewolfDayVoteSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:

        if not WerewolfDayVoteSystem.is_day_discussion_complete(self._game):
            logger.info("白天讨论还没有完成，不能进行投票")
            return

        # 获取所有存活的玩家（用于投票）
        alive_players = self._game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        if len(alive_players) == 0:
            logger.warning("没有存活的玩家，无法进行投票")
            return

        logger.info(f"开始投票阶段，存活玩家数量: {len(alive_players)}")

        # 创建投票推理的prompt示例
        response_sample = DayVoteResponse(
            mind_voice="基于前面的讨论，我认为某某玩家最可疑，因为...",
            target_name="目标玩家姓名",
        )

        # 获取所有存活玩家的姓名列表，用于投票选择
        alive_player_names = [player.name for player in alive_players]

        vote_prompt = f"""# 现在是投票阶段，你需要根据前面的讨论内容选择一个玩家进行投票

## 当前存活玩家
{', '.join(alive_player_names)}

## 投票要求
1. 根据前面的讨论分析每个玩家的发言
2. 推理谁最可能是狼人
3. 选择一个你认为应该被投票出局的玩家
4. target_name 必须是存活玩家列表中的一个确切姓名

## 输出格式

### 标准示例

```json
{response_sample.model_dump_json()}
```

## 输出要求

请严格按照上述的 JSON 标准示例 格式输出！target_name 必须是存活玩家中的一个！"""

        # 为每个玩家创建投票请求
        request_handlers: List[ChatClient] = []
        for player in alive_players:
            agent_memory = self._game.get_agent_chat_history(player)
            request_handlers.append(
                ChatClient(
                    name=player.name,
                    prompt=vote_prompt,
                    chat_history=agent_memory.chat_history,
                )
            )

        # 批量发送投票推理请求
        await ChatClient.gather_request_post(clients=request_handlers)

        logger.info("=== 投票结果 ===")

        for request2 in request_handlers:

            entity2 = self._game.get_entity_by_name(request2.name)
            if entity2 is None:
                logger.error(f"无法找到玩家实体: {request2.name}")
                continue

            try:
                format_response = DayVoteResponse.model_validate_json(
                    json_format.strip_json_code_block(request2.response_content)
                )

                if format_response.mind_voice != "":
                    entity2.replace(
                        MindVoiceAction, entity2.name, format_response.mind_voice
                    )

                if format_response.target_name != "":
                    entity2.replace(
                        VoteAction, entity2.name, format_response.target_name
                    )

            except Exception as e:
                logger.error(f"Exception: {e}")

        # 清除所有玩家的 DayDiscussionFlagComponent 标记。
        all1 = self._game.get_group(
            Matcher(
                all_of=[DayDiscussionFlagComponent],
            )
        ).entities.copy()
        for player in all1:
            player.remove(DayDiscussionFlagComponent)

        # 清除所有玩家的 NightKillFlagComponent 标记。
        all2 = self._game.get_group(
            Matcher(
                all_of=[NightKillFlagComponent],
            )
        ).entities.copy()
        for player in all2:
            player.remove(NightKillFlagComponent)

    ###############################################################################################################################################
    @staticmethod
    def is_day_discussion_complete(game: TCGGame) -> bool:
        players1 = game.get_group(
            Matcher(
                all_of=[DayDiscussionFlagComponent],
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
                # none_of=[DeathComponent],
            )
        ).entities.copy()

        players2 = game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        logger.info(
            f"讨论完成标记玩家数量: {len(players1)} / 存活玩家数量: {len(players2)}"
        )

        return len(players1) >= len(players2)

    ###############################################################################################################################################
