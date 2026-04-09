"""出牌叙事润色系统模块。

在 EnemyPlayDecisionSystem 之后、PlayCardsActionSystem 之前触发。
当 PlayCardsAction.action 为空且卡牌非空时，调用 LLM 为出牌者生成
第一人称行动叙事，回写至 PlayCardsAction。

该系统是可选的：即使不加入 pipeline，ArbitrationActionSystem 也有兜底逻辑。
"""

from typing import Final, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    PlayCardsAction,
    CharacterStatsComponent,
    DeathComponent,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class ActionNarrationResponse(BaseModel):
    """出牌叙事响应模型"""

    action: str


#######################################################################################################################################
def _generate_narration_prompt(
    actor_name: str,
    play_cards_action: PlayCardsAction,
    targets: List[str],
    current_round_number: int,
) -> str:
    card = play_cards_action.card
    targets_str = "、".join(t.split(".")[-1] for t in targets) if targets else "无目标"

    return f"""# 第 {current_round_number} 回合：出牌叙事（以 JSON 格式返回）

你是 {actor_name}，请以**第一人称**为本次出牌写 1-2 句生动叙事。

卡牌：{card.name}（{card.description}）
目标：{targets_str}

结合卡牌描述与当前战场情境，不要提及具体数字或术语。

```json
{{
  "action": "第一人称出牌叙事（1-2句）"
}}
```"""


#######################################################################################################################################
@final
class PlayActionNarrationSystem(ReactiveProcessor):
    """出牌叙事润色系统。

    当 PlayCardsAction.action 为空时，调用 LLM 为出牌者生成第一人称行动叙事，
    并将结果回写至 PlayCardsAction。仅处理非空卡（card.name != ""）。
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlayCardsAction)
            and entity.has(CharacterStatsComponent)
            and not entity.has(DeathComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("PlayActionNarrationSystem: 战斗未进行中，跳过")
            return

        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        # 只为 action 为空且卡牌非空的实体创建 ChatClient
        chat_clients: List[ChatClient] = []
        for entity in entities:
            action = entity.get(PlayCardsAction)
            if action.action != "" or action.card.name == "":
                continue

            prompt = _generate_narration_prompt(
                actor_name=entity.name,
                play_cards_action=action,
                targets=action.targets,
                current_round_number=current_round_number,
            )
            chat_clients.append(
                ChatClient(
                    name=entity.name,
                    prompt=prompt,
                    context=self._game.get_agent_context(entity).context,
                )
            )

        if not chat_clients:
            logger.debug("PlayActionNarrationSystem: 无需润色的出牌，跳过")
            return

        logger.debug(
            f"PlayActionNarrationSystem: 为 {len(chat_clients)} 个出牌生成叙事"
        )

        await ChatClient.batch_chat(clients=chat_clients)

        for client in chat_clients:
            found = self._game.get_entity_by_name(client.name)
            assert (
                found is not None
            ), f"PlayActionNarrationSystem: 无法找到实体 {client.name}"
            # if found is None:
            #     logger.error(f"PlayActionNarrationSystem: 无法找到实体 {client.name}")
            #     continue
            self._apply_narration(found, client)

    #######################################################################################################################################
    def _apply_narration(self, entity: Entity, client: ChatClient) -> None:
        """解析 LLM 响应并回写至 PlayCardsAction.action。失败时记录错误日志，保持原有空字符串不变，由仲裁系统兜底。"""
        try:
            response = ActionNarrationResponse.model_validate_json(
                extract_json_from_code_block(client.response_content)
            )
            play_cards_action = entity.get(PlayCardsAction)
            entity.replace(
                PlayCardsAction,
                play_cards_action.name,
                play_cards_action.card,
                play_cards_action.targets,
                response.action,
            )
            logger.debug(
                f"PlayActionNarrationSystem: [{entity.name}] 叙事生成完毕 | {response.action}"
            )
        except Exception as e:
            logger.error(
                f"PlayActionNarrationSystem: [{entity.name}] 解析叙事失败，将使用仲裁兜底。Exception: {e}"
            )

    #######################################################################################################################################
