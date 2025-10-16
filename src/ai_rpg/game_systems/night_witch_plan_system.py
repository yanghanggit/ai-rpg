from typing import final, Tuple, List
from overrides import override
from pydantic import BaseModel
from ..entitas import Entity, Matcher, GroupEvent, ReactiveProcessor
from ..game.tcg_game import TCGGame
from loguru import logger
from ..models import (
    InventoryComponent,
    WitchComponent,
    DeathComponent,
    WerewolfComponent,
    SeerComponent,
    VillagerComponent,
    # WolfKillAction,
    WitchPoisonAction,
    WitchCureAction,
    NightPlanComponent,
    MindVoiceAction,
    NightKillComponent,
)
from ..utils.md_format import format_list_as_markdown_list
from ..chat_services.client import ChatClient
from ..utils import json_format


@final
class WitchDecisionResponse(BaseModel):
    mind_voice: str
    cure_target: str
    poison_target: str


def _generate_prompt(list_items_prompt: str, status_info: List[Tuple[str, str]]) -> str:

    response_sample = WitchDecisionResponse(
        mind_voice="你内心独白，你的想法已经你为什么要这么决策",
        cure_target="目标的全名 或者 空字符串 表示不救人",
        poison_target="目标的全名 或者 空字符串 表示不毒人",
    )

    return f"""# 指令！作为女巫，你将决定夜晚的行动。
        
## 你的道具信息

{list_items_prompt}

## 当前可选的查看目标:

{format_list_as_markdown_list(status_info)}

## 决策建议

作为女巫，你应该考虑以下因素来决定你的行动：
1. **救人**: 当你有解药时，如果有玩家被狼人杀害，你可以选择使用解药救活其中一人。考虑救谁时，可以基于该玩家的角色重要性（如预言家）或游戏策略（如怀疑某人为狼人）。
2. **毒人**: 当你有毒药时，你也可以选择使用毒药毒杀一名存活的玩家。选择毒谁时，可以基于你对其他玩家的怀疑或游戏策略。
3. **资源管理**: 记住，你只有一瓶解药和一瓶毒药，每种只能使用一次。合理利用这些资源是关键，并且保证在你临死前有机会使用。
4. **游戏局势**: 考虑当前的游戏局势和其他玩家的行为，做出最有利于你阵营的决策。
5. **自保**: 如果你被杀害，但是你有解药，你应该优先考虑救自己。

## 注意事项

- 你每个回合只能使用一种药剂，或者救人，或者毒人，或者什么都不做。

## 输出格式

### 标准示例

```json
{response_sample.model_dump_json()}
```

## 输出要求

请严格按照上述的 JSON 标准示例 格式输出！你必须从上述可选目标中选择一个作为target_name。 如果你决定不救人或不毒人，请将对应的字段填写为空字符串。"""


###############################################################################################################################################
@final
class NightWitchPlanSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(NightPlanComponent): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(NightPlanComponent) and entity.has(WitchComponent)

    #######################################################################################################################################

    ###############################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """女巫夜晚行动的主流程"""
        assert len(entities) == 1, "不可能有多个女巫同时行动"

        # 一个女巫
        witch_entity = entities[0]

        # 本夜晚被狼人杀害的人！
        victims_of_wolf = self._game.get_group(
            Matcher(
                any_of=[NightKillComponent],
            )
        ).entities.copy()

        # 所有还活着的玩家
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

        # 玩家状态信息
        victim_survivor_status: List[Tuple[str, str]] = []
        for one in victims_of_wolf:
            victim_survivor_status.append((one.name, "今夜被杀害"))

        for one in alive_players:
            # if one not in victims_of_wolf:
            victim_survivor_status.append((one.name, "存活中"))

        # 女巫的道具信息
        inventory_component = witch_entity.get(InventoryComponent)
        assert inventory_component is not None

        # 生成 prompt
        prompt = _generate_prompt(
            inventory_component.list_items_prompt, victim_survivor_status
        )

        # 获取上下文。
        witch_agent_memory = self._game.get_agent_chat_history(witch_entity)

        # 构建请求处理器
        request_handler = ChatClient(
            name=witch_entity.name,
            prompt=prompt,
            chat_history=witch_agent_memory.chat_history,
        )

        # 执行请求
        await ChatClient.gather_request_post(clients=[request_handler])

        try:

            # 解析女巫的决策
            response = WitchDecisionResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.response_content)
            )

            # 如果有内心独白，则需要添加行动
            if response.mind_voice != "":
                witch_entity.replace(
                    MindVoiceAction, witch_entity.name, response.mind_voice
                )

            # 是否救人？
            if response.cure_target != "":

                # 获取救治目标实体
                cure_target_entity = self._game.get_actor_entity(response.cure_target)
                assert cure_target_entity is not None, "找不到救治目标实体"
                if cure_target_entity is not None:

                    # 执行救人行动
                    cure_target_entity.replace(
                        WitchCureAction, cure_target_entity.name, witch_entity.name
                    )

                else:

                    # 目标实体不存在
                    logger.error(
                        f"女巫 {witch_entity.name} 想要救的玩家 {response.cure_target} 不存在，跳过救人"
                    )

            # 是否毒人？
            if response.poison_target != "":

                # 获取毒人目标实体
                poison_target_entity = self._game.get_actor_entity(
                    response.poison_target
                )
                assert poison_target_entity is not None, "找不到毒人目标实体"
                if poison_target_entity is not None:

                    # 执行毒人行动
                    poison_target_entity.replace(
                        WitchPoisonAction, poison_target_entity.name, witch_entity.name
                    )
                else:

                    # 目标实体不存在
                    logger.error(
                        f"女巫 {witch_entity.name} 想要毒的玩家 {response.poison_target} 不存在，跳过毒人"
                    )

            # 最终什么都不做？
            if response.cure_target == "" and response.poison_target == "":

                # 什么都不做，就是添加上下文即可。
                witch_entity.replace(
                    MindVoiceAction,
                    witch_entity.name,
                    "决定本轮不使用任何道具，跳过女巫行动。",
                )

        except Exception as e:

            logger.error(f"Exception: {e}")

            # 保底添加上下文，也是跳过女巫行动
            self._game.append_human_message(
                witch_entity,
                f"""# 提示！在解析你的决策时出现错误。本轮你将跳过女巫行动。""",
            )

    ###############################################################################################################################################
