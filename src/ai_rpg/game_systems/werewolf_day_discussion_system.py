from typing import final, List
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..entitas import ExecuteProcessor, Matcher
from ..game.sd_game import SDGame
from ..models import (
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    DeathComponent,
    DayDiscussedComponent,
    DiscussionAction,
    MindEvent,
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
    def __init__(self, game_context: SDGame) -> None:
        self._game: SDGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:

        if self._game._werewolf_game_turn_counter == 2:

            logger.warning("第一个白天讨论")

            # 第一个白天是特殊的，所有人尚未讨论过的人都可以发言
            alive_players = self._game.get_group(
                Matcher(
                    any_of=[
                        WerewolfComponent,
                        SeerComponent,
                        WitchComponent,
                        VillagerComponent,
                    ],
                    none_of=[DayDiscussedComponent],
                )
            ).entities.copy()

        else:

            # logger.debug("非第一个白天讨论")

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
                        DayDiscussedComponent,
                        DeathComponent,
                    ],
                )
            ).entities.copy()

        if len(alive_players) == 0:
            logger.warning(
                "没有存活的玩家，或者都已经讨论过了，所以不用进入白天讨论!!!!!!!"
            )
            return

        selected_entity = random.choice(list(alive_players))

        # logger.debug(f"选择玩家 {selected_entity.name} 进行白天讨论")

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

## 注意
1. 严格遵循推理机制
2. 如果你是狼人，你一定会冒充预言家或者女巫来骗取村民的信任。
3. 如果你是村民，你需要注意分辨，预言家和女巫有可能是狼人冒充的。
4. 如果你是女巫或者预言家，如果有人冒充你，你需要揭穿他，并且他是你重点怀疑的对象。
5. 如果你要冒充女巫，你需要知道以下信息做为冒充的基础：
    解药：可以救活当晚被狼人杀害的玩家，整局游戏只能使用一次。
    毒药：可以毒死任意一名玩家，整局游戏只能使用一次。
    每晚最多只能使用一种药剂，也可以选择不使用。
    如果昨晚是平安夜，说明女巫使用了解药。
    如果昨晚死了两个人，说明女巫使用了毒药。
    解药和毒药一定会使用成功。

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

        try:
            response = DayDiscussionResponse.model_validate_json(
                json_format.strip_json_code_block(request_handlers[0].response_content)
            )

            if response.mind_voice != "":

                self._game.notify_entities(
                    set({selected_entity}),
                    MindEvent(
                        message=f"{selected_entity.name} : {response.mind_voice}",
                        actor=selected_entity.name,
                        content=response.mind_voice,
                    ),
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
            DayDiscussedComponent,
            selected_entity.name,
            request_handlers[0].response_content,
        )

    ###############################################################################################################################################
