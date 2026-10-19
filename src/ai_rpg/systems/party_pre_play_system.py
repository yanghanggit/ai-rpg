"""出牌前系统模块（队员）。

预留 hook：与 `MonsterPrePlaySystem` 结构对齐，供将来「出牌前注入」类机制挂载。
队员在战斗中的决策来自第四面墙外的玩家（前端指令），不产生 LLM 推理由此不由本系统承担，
所以当前实现只有结构（触发条件 + 战斗态校验），没有推理与记忆写入。
"""

from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    DeathComponent,
    HandComponent,
    PartyMemberComponent,
    PlayCardsAction,
)


#######################################################################################################################################
@final
class PartyPrePlaySystem(ReactiveProcessor):
    """出牌前系统（队员）：预留 hook，当前不写入记忆。

    队员的出牌决策由玩家侧给出（命令即决策），不存在"决策 LLM"，因此这里没有
    `MonsterPrePlaySystem` 那样的「请求原文 + 回包原文」留痕；出牌记录由
    `PlayCardsActionSystem` 的 `play_card_record` 统一承担。
    """

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlayCardsAction)
            and entity.has(HandComponent)
            and entity.has(PartyMemberComponent)
            and not entity.has(DeathComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("PartyPrePlaySystem: 战斗未进行中，跳过")
            return

        logger.debug(
            f"PartyPrePlaySystem: 触发出牌前处理，找到 {len(entities)} 个符合条件的出牌实体"
        )

    #######################################################################################################################################
