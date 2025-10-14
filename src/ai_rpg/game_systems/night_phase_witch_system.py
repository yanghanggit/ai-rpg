from typing import final, Tuple, List
from overrides import override
from pydantic import BaseModel
from ..entitas import Entity, Matcher, GroupEvent
from loguru import logger
from ..models import (
    InventoryComponent,
    WitchComponent,
    DeathComponent,
    WerewolfComponent,
    SeerComponent,
    VillagerComponent,
    WolfKillAction,
    WitchPoisonAction,
    WitchCureAction,
    NightPhaseAction,
    AgentEvent,
)
from ..utils.md_format import format_list_as_markdown_list
from ..chat_services.client import ChatClient
from ..utils import json_format
from .base_action_reactive_system import BaseActionReactiveSystem


@final
class WitchDecisionResponse(BaseModel):
    mind_voice: str
    cure_target: str
    poison_target: str


###############################################################################################################################################
@final
class NightPhaseWitchSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(NightPhaseAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(NightPhaseAction) and entity.has(WitchComponent)

    #######################################################################################################################################

    ###############################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """女巫夜晚行动的主流程"""
        assert len(entities) == 1, "不可能有多个女巫同时行动"
        logger.info("女巫请睁眼，选择你要救的玩家或毒的玩家")

        # 一个女巫
        witch_entity = entities[0]

        # 被狼人杀害的
        killed = self._game.get_group(
            Matcher(
                all_of=[
                    WolfKillAction,
                ],
            )
        ).entities.copy()

        # 所有的人。
        all = self._game.get_group(
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

        status_info: List[Tuple[str, str]] = []
        for one in all:
            if one in killed:
                status_info.append((one.name, "被杀害"))
            else:
                status_info.append((one.name, "存活中"))

        logger.info(f"当前玩家状态: {status_info}")

        response_sample = WitchDecisionResponse(
            mind_voice="你内心独白，你的想法已经你为什么要这么决策",
            cure_target="目标的全名 或者 空字符串 表示不救人",
            poison_target="目标的全名 或者 空字符串 表示不毒人",
        )

        inventory_component = witch_entity.get(InventoryComponent)
        assert inventory_component is not None

        prompt = f"""# 指令！作为女巫，你将决定夜晚的行动。
        
## 你的道具信息

{inventory_component.list_items_prompt}

## 当前可选的查看目标:

{format_list_as_markdown_list(status_info)}

## 决策建议

作为女巫，你应该考虑以下因素来决定你的行动：
1. **救人**: 如果有玩家被狼人杀害，你可以选择使用解药救活其中一人。考虑救谁时，可以基于该玩家的角色重要性（如预言家）或游戏策略（如怀疑某人为狼人）。
2. **毒人**: 你也可以选择使用毒药毒杀一名存活的玩家。选择毒谁时，可以基于你对其他玩家的怀疑或游戏策略。
3. **资源管理**: 记住，你只有一瓶解药和一瓶毒药，每种只能使用一次。合理利用这些资源是关键。
4. **游戏局势**: 考虑当前的游戏局势和其他玩家的行为，做出最有利于你阵营的决策。

## 输出格式

### 标准示例

```json
{response_sample.model_dump_json()}
```

## 输出要求

请严格按照上述的 JSON 标准示例 格式输出！你必须从上述可选目标中选择一个作为target_name。 如果你决定不救人或不毒人，请将对应的字段填写为空字符串。"""

        agent_short_term_memory = self._game.get_agent_chat_history(witch_entity)
        request_handler = ChatClient(
            name=witch_entity.name,
            prompt=prompt,
            chat_history=agent_short_term_memory.chat_history,
        )

        # 执行请求
        await ChatClient.gather_request_post(clients=[request_handler])

        try:
            response = WitchDecisionResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.response_content)
            )

            if response.mind_voice != "":
                self._game.append_human_message(
                    witch_entity,
                    f"""# 提示！你内心独白: {response.mind_voice}""",
                )

            # 是否救人？
            if response.cure_target != "":
                cure_target_entity = self._game.get_actor_entity(response.cure_target)
                assert cure_target_entity is not None, "找不到救治目标实体"
                if cure_target_entity is not None:
                    cure_target_entity.replace(
                        WitchCureAction, cure_target_entity.name, witch_entity.name
                    )
                else:
                    logger.error(
                        f"女巫 {witch_entity.name} 想要救的玩家 {response.cure_target} 不存在，跳过救人"
                    )

            # 是否毒人？
            if response.poison_target != "":
                poison_target_entity = self._game.get_actor_entity(
                    response.poison_target
                )
                assert poison_target_entity is not None, "找不到毒人目标实体"
                if poison_target_entity is not None:
                    poison_target_entity.replace(
                        WitchPoisonAction, poison_target_entity.name, witch_entity.name
                    )
                else:
                    logger.error(
                        f"女巫 {witch_entity.name} 想要毒的玩家 {response.poison_target} 不存在，跳过毒人"
                    )

            # 最终什么都不做？
            if response.cure_target == "" and response.poison_target == "":
                self._game.notify_event(
                    set({witch_entity}),
                    AgentEvent(
                        message=f"""# 提示！你决定本轮不使用任何道具，跳过女巫行动。""",
                    ),
                )

        except Exception as e:
            logger.error(f"Exception: {e}")
            self._game.append_human_message(
                witch_entity,
                f"""# 提示！在解析你的决策时出现错误。本轮你将跳过女巫行动。""",
            )

    ###############################################################################################################################################
