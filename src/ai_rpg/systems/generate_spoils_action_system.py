"""奖励(Spoils)生成系统：从卡牌原型库随机抽取 N 个原型，交由角色 agent 设计后装入 SpoilsComponent 供后续领取。

本系统只负责「候选选取 + 最终去向」：随机抽原型、物化候选，交给 `card_common`
引擎完成实际设计，最后把设计好的卡写进 `SpoilsComponent`。

失败语义：LLM 出错就没有结果。设计会话未把全部候选落地（agent_loop 失败 / 有卡
未提交 / 中途异常）时，该角色本次**不写 SpoilsComponent**（也因此不发「待领取」
记忆），绝不把带原型原名与引导词缀的半成品发给玩家；客户端可重新触发一次。
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
    MotifComponent,
    SpoilsComponent,
)
from ..pgsql import CardPrototypeIndexEntry, list_card_prototype_index
from ..utils import batch_run_boolean_tasks
from .card_common import (
    Candidate,
    design_cards_for_actor,
    materialize_candidate,
    read_actor_system_prompt,
)
from .card_pile_common import PILE_SPOILS, format_card_names, record_pile_change

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
                    f"[GenerateSpoilsActionSystem] {entity.name} 候选物化失败，整批中止，未写入任何 SpoilsComponent（客户端可重试）"
                )
                return
            materialized.append((entity, candidates))

        # 第二步：并发跑卡牌设计会话。
        # 上下文 = 卡牌设计世界实体的契约 + 该角色自己的 system prompt；会话不写入角色记忆，
        # 因此在战利品阶段，角色除「pick」之外并不知道这些卡是怎么来的。
        tasks: List[Tuple[str, Coroutine[Any, Any, bool]]] = [
            (entity.name, self._design_candidates(entity, candidates))
            for entity, candidates in materialized
        ]

        if not tasks:
            logger.debug("[GenerateSpoilsActionSystem] 无待生成奖励的角色")
            return

        logger.info(
            f"[GenerateSpoilsActionSystem] 为 {len(tasks)} 个角色并发生成候选奖励..."
        )
        outcomes = await batch_run_boolean_tasks(tasks)

        # 第三步：装入 Spoils（replace 覆盖旧内容；claimed_cards 为空队列）。
        # 设计失败的实体直接跳过：LLM 出错就没有结果，宁可不发也不发半成品。
        for (entity, candidates), ok in zip(materialized, outcomes):
            if not ok:
                logger.warning(
                    f"[GenerateSpoilsActionSystem] {entity.name} 设计会话未完成，本次不写 SpoilsComponent（LLM 出错即无结果，客户端可重新触发）"
                )
                continue

            spoils_before = (
                len(entity.get(SpoilsComponent).candidate_cards)
                if entity.has(SpoilsComponent)
                else 0
            )
            spoils_cards = [c.card for c in candidates]
            entity.replace(SpoilsComponent, entity.name, spoils_cards, [])

            # 待领取队列变了：让主人知道现在有哪些牌可以领
            if len(spoils_cards) != spoils_before:
                record_pile_change(
                    self._game,
                    entity,
                    change="spoils_generate",
                    title="待领取的奖励",
                    lines=[
                        f"待领取队列现有 {len(spoils_cards)} 张：{format_card_names(spoils_cards)}",
                        "挑一张收下，它会进入你的牌库。",
                    ],
                    deltas={PILE_SPOILS: len(spoils_cards) - spoils_before},
                )

            logger.info(
                f"[GenerateSpoilsActionSystem] {entity.name}: 候选卡 {len(candidates)} 张已设计完成"
            )

    ####################################################################################################################################
    async def _design_candidates(
        self, entity: Entity, candidates: List[Candidate]
    ) -> bool:
        """为单个角色跑设计会话；仅当全部候选都落地完成才算成功。

        `DesignOutcome` 可能 `ok=True` 但 `designed < total`（agent 提前结束未提交全部卡），
        这种情况下候选仍带着原型原名与引导词缀，不能当成功发放。
        角色挂载了 `MotifComponent` 时，其 `motif` 作为艺术锚点注入；未挂则沿用旧口径。
        """
        motif = entity.get(MotifComponent).motif if entity.has(MotifComponent) else ""
        outcome = await design_cards_for_actor(
            self._game,
            actor_name=entity.name,
            actor_system_prompt=read_actor_system_prompt(self._game, entity),
            candidates=candidates,
            actor_motif=motif,
            max_rounds=6,
        )
        return bool(outcome.ok and outcome.designed == len(candidates))

    ####################################################################################################################################
    def _materialize_candidates(
        self,
        entity: Entity,
        index: List[CardPrototypeIndexEntry],
    ) -> List[Candidate]:
        """物化候选：有显式规格就按规格（顺序、重复照给），否则从原型索引随机抽取。

        显式规格（调测 / 脚本入口写入 ``GenerateSpoilsAction.prototype_ids``）把“候选是什么”
        从随机里拿回来；任一原型物化失败即返回空列表（整批中止），避免静默少发一张。
        随机路径保持旧口径：个别原型解析失败只跳过，不阻断发奖。
        """
        action = entity.get(GenerateSpoilsAction)
        forced = list(action.prototype_ids) if action is not None else []

        if forced:

            # 使用显式候选规格时，记录日志以便调试。
            logger.info(
                f"[GenerateSpoilsActionSystem] {entity.name} 使用显式候选规格（{len(forced)} 张）: {forced}"
            )
            prototype_ids = forced
        else:

            # 随机抽取原型时，记录日志以便调试。
            prototype_ids = [
                entry["prototype_id"]
                for entry in random.sample(index, k=min(SPOILS_CARD_COUNT, len(index)))
            ]

        candidates: List[Candidate] = []
        for prototype_id in prototype_ids:
            candidate = materialize_candidate(prototype_id, entity.name)

            # 如果显式规格物化失败，整批中止；否则跳过该原型继续尝试下一个。
            if candidate is None:
                if forced:
                    logger.error(
                        f"[GenerateSpoilsActionSystem] {entity.name} 显式原型 {prototype_id!r} 物化失败，整批中止"
                    )
                    return []
                continue

            # 成功物化的候选加入列表，供后续设计使用。
            candidates.append(candidate)

        # 返回最终物化成功的候选列表，供后续设计使用。
        return candidates
