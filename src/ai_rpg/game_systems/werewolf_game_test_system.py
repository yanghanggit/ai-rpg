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
)
import random
from ..chat_services.client import ChatClient
from ..utils import json_format

###############################################################################################################################################


###############################################################################################################################################
@final
class TestResponse(BaseModel):
    mind_voice: str
    discussion: str


###############################################################################################################################################
@final
class WerewolfGameTestSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        logger.info(f"狼人杀测试系统启动 = {self._game._time_marker}")
        assert self._game._time_marker % 2 == 0, "time_marker 必须是偶数"

        alive_players = self._game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
                none_of=[DeathComponent, DayDiscussionFlagComponent],
            )
        ).entities.copy()

        if len(alive_players) == 0:
            logger.warning("没有存活的玩家，或者都已经讨论过了，所以不用进入白天讨论")
            return

        selected_entity = random.choice(list(alive_players))

        response_sample = TestResponse(
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
            response = TestResponse.model_validate_json(
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

        # selected_entity.replace(
        #     DiscussionAction, selected_entity.name, request_handlers[0].response_content
        # )

    ###############################################################################################################################################
