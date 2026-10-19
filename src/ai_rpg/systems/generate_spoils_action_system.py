"""奖励(Spoils)生成系统：从卡牌原型库随机抽取 N 个原型，交由角色 agent 设计后装入 SpoilsComponent 供后续领取。

本系统只负责「候选选取 + 最终去向」：随机抽原型、物化候选，交给 `card_common`
引擎完成实际设计，最后把设计好的卡写进 `SpoilsComponent`。
"""

import random
from typing import Any, Coroutine, Dict, Final, List, Tuple, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    DeathComponent,
    GenerateSpoilsAction,
    SpoilsComponent,
)
from ..pgsql import CardPrototypeIndexEntry, list_card_prototype_index
from ..utils import batch_run_boolean_tasks
from .card_common import (
    Candidate,
    materialize_candidate,
    run_card_design_session,
)

#######################################################################################################################################
SPOILS_CARD_COUNT: Final[int] = 3  # 候选卡数量（3 选 1），未来可调


#######################################################################################################################################
@final
class GenerateSpoilsActionSystem(ReactiveProcessor):
    """响应奖励生成动作，为触发角色从原型库抽取候选卡、交由 agent 设计后装入 SpoilsComponent。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(GenerateSpoilsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(GenerateSpoilsAction)
            and entity.has(ActorComponent)
            and not entity.has(DeathComponent)
            and not entity.has(SpoilsComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        # 拉取一次原型索引（系统侧随机，不用 LLM 浏览）
        try:
            index = list_card_prototype_index(card_type="手牌")
        except Exception as e:
            logger.error(f"[GenerateSpoilsActionSystem] 拉取卡牌原型失败: {e}")
            return

        if not index:
            logger.error(
                "[GenerateSpoilsActionSystem] 卡牌原型库为空，无法生成候选奖励"
            )
            return

        # 第一步：整批物化候选；任一角色物化失败则整批中止（全有或全无，客户端可重试）
        materialized: List[Tuple[Entity, List[Candidate]]] = []
        for entity in entities:
            candidates = self._materialize_candidates(entity, index)
            if not candidates:
                logger.error(
                    f"[GenerateSpoilsActionSystem] {entity.name} 候选物化失败，"
                    f"整批中止，未写入任何 SpoilsComponent（客户端可重试）"
                )
                return
            materialized.append((entity, candidates))

        # 第二步：并发跑卡牌设计会话（LLM 设计失败不阻断发奖，只影响设计）
        tasks: List[Tuple[str, Coroutine[Any, Any, Any]]] = [
            (
                entity.name,
                run_card_design_session(
                    name=entity.name,
                    candidates=candidates,
                    messages=self._game.get_agent_memory(entity).messages,
                    max_rounds=6,
                ),
            )
            for entity, candidates in materialized
        ]

        if not tasks:
            logger.debug("[GenerateSpoilsActionSystem] 无待生成奖励的角色")
            return

        logger.info(
            f"[GenerateSpoilsActionSystem] 为 {len(tasks)} 个角色并发生成候选奖励..."
        )
        outcomes = await batch_run_boolean_tasks(tasks)

        # 第三步：装入 Spoils（replace 覆盖旧内容；claimed_cards 为空队列）
        for (entity, candidates), ok in zip(materialized, outcomes):
            entity.replace(
                SpoilsComponent, entity.name, [c.card for c in candidates], []
            )
            logger.info(
                f"[GenerateSpoilsActionSystem] {entity.name}: 候选卡 {len(candidates)} 张"
                f"（agent_loop 成功={ok}）"
            )

    ####################################################################################################################################
    def _materialize_candidates(
        self,
        entity: Entity,
        index: List[CardPrototypeIndexEntry],
    ) -> List[Candidate]:
        """从原型索引随机抽取并物化为独立候选（换新 uuid、回填 source、附设计说明）。"""
        sample = random.sample(index, k=min(SPOILS_CARD_COUNT, len(index)))
        candidates: List[Candidate] = []
        for entry in sample:
            candidate = materialize_candidate(entry["prototype_id"], entity.name)
            if candidate is not None:
                candidates.append(candidate)
        return candidates
