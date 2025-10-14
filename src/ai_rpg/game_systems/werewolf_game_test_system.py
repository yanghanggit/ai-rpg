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
    DiscussionAction,
    MindVoiceAction,
    NightKillFlagComponent,
    VoteAction,
    MindVoiceAction,
)
import random
from ..chat_services.client import ChatClient
from ..utils import json_format

###############################################################################################################################################


###############################################################################################################################################
@final
class DayDiscussionResponse(BaseModel):
    mind_voice: str
    discussion: str


###############################################################################################################################################
@final
class WerewolfDayDiscussionSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        # return  # 先屏蔽掉白天讨论系统
        logger.info(f"狼人杀测试系统启动 = {self._game._time_marker}")
        assert self._game._time_marker % 2 == 0, "time_marker 必须是偶数"

        if self._game._time_marker == 2:

            # 第一个白天是特殊的，所有人尚未讨论过的人都可以发言
            alive_players = self._game.get_group(
                Matcher(
                    any_of=[
                        WerewolfComponent,
                        SeerComponent,
                        WitchComponent,
                        VillagerComponent,
                    ],
                    none_of=[DayDiscussionFlagComponent],
                )
            ).entities.copy()

        else:

            # 从此后每个白天，只能活着的且没讨论过的玩家可以发言
            alive_players = self._game.get_group(
                Matcher(
                    any_of=[
                        WerewolfComponent,
                        SeerComponent,
                        WitchComponent,
                        VillagerComponent,
                    ],
                    none_of=[
                        DeathComponent,
                        DayDiscussionFlagComponent,
                        NightKillFlagComponent,
                    ],
                )
            ).entities.copy()

        if len(alive_players) == 0:
            logger.warning("没有存活的玩家，或者都已经讨论过了，所以不用进入白天讨论")
            return

        selected_entity = random.choice(list(alive_players))

        response_sample = DayDiscussionResponse(
            mind_voice="你此时的内心想法，你为什么要如此的发言。",
            discussion="你要发言的内容",
        )

        prompt = f"""# 现在是白天讨论时间，你需要进行发言，讨论内容可以包括但不限于以下几点：
1. 分享昨晚的经历和发现
2. 猜测谁是狼人
3. 提出投票建议
4. 讨论村庄的整体策略
5. 任何其他与游戏相关的讨论

## 输出格式

### 标准示例

```json
{response_sample.model_dump_json()}
```

## 输出要求

请严格按照上述的 JSON 标准示例 格式输出！"""

        agent_memory = self._game.get_agent_chat_history(selected_entity)

        request_handlers: List[ChatClient] = []
        request_handlers.append(
            ChatClient(
                name=selected_entity.name,
                prompt=prompt,
                chat_history=agent_memory.chat_history,
            )
        )

        await ChatClient.gather_request_post(clients=request_handlers)

        logger.debug(
            f"玩家 {selected_entity.name} 进入白天讨论 = \n{request_handlers[0].response_content}"
        )

        try:
            response = DayDiscussionResponse.model_validate_json(
                json_format.strip_json_code_block(request_handlers[0].response_content)
            )

            if response.mind_voice != "":
                selected_entity.replace(
                    MindVoiceAction, selected_entity.name, response.mind_voice
                )

            if response.discussion != "":
                selected_entity.replace(
                    DiscussionAction, selected_entity.name, response.discussion
                )

        except Exception as e:
            logger.error(f"Exception: {e}")
            # 出现异常时，添加一个默认的讨论动作
            selected_entity.replace(
                DiscussionAction, selected_entity.name, "我选择保持沉默。"
            )

        selected_entity.replace(
            DayDiscussionFlagComponent,
            selected_entity.name,
            request_handlers[0].response_content,
        )

    ###############################################################################################################################################


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

        if not self._is_day_discussion_complete():
            logger.info("白天讨论还没有完成，不能进行投票")
            return

        # while True:
        #     input(f"所有发言完毕，任意键发起投票:")
        #     break
        #     # if usr_input.strip() != "":
        #     #     break

        # 获取所有存活的玩家（用于投票）
        alive_players = self._game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
                none_of=[DeathComponent, NightKillFlagComponent],
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
    def _is_day_discussion_complete(self) -> bool:
        players1 = self._game.get_group(
            Matcher(
                all_of=[DayDiscussionFlagComponent],
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
            )
        ).entities.copy()

        players2 = self._game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
            )
        ).entities.copy()

        return len(players1) >= len(players2)

    ###############################################################################################################################################
