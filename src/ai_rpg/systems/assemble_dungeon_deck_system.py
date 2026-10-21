"""副本怪物牌库组建系统：为每个战斗房间的怪物组建初始牌库。

选型与设计都复用卡牌公共层，本系统只负责「组装 + 兜底」；两阶段都以怪物自己的
system message 作为唯一且临时上下文，结束后不写回持久记忆。
"""

import json
from pathlib import Path
from typing import (
    Any,
    Coroutine,
    Dict,
    Final,
    List,
    Optional,
    Tuple,
    final,
)
from uuid import uuid4

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    Actor,
    Card,
    CombatRoom,
    DeckComponent,
    Dungeon,
    DungeonDraft,
    GenerateDungeonAction,
)
from ..paths import DUNGEONS_DIR
from ..pgsql import (
    CardPrototypeIndexEntry,
    get_default_deck_card_jsons,
    list_card_prototype_index,
)
from ..utils import batch_run_boolean_tasks, prompt_builder
from .card_common import (
    Candidate,
    design_cards_for_actor,
    materialize_candidate,
    read_motif_from_components,
    select_prototypes_for_actor,
)


####################################################################################################################################
def make_default_deck_cards(owner: str) -> List[Card]:
    """默认牌库：直接取数据库中的「默认牌单」，给什么用什么。

    牌单由 demo/card_prototypes.py 的 `DEFAULT_DECK_BUILD` 经 setup_demo 灌库，
    本函数不关心任何卡名与份数，仅按返回顺序逐张物化为独立 Card。
    `source` 回填为持有者名（牌库入口不变量：预制/兜底牌库的每张牌都必须带 source）。
    """
    cards: List[Card] = []
    for card_json in get_default_deck_card_jsons():
        card = Card.model_validate(json.loads(card_json))
        card.uuid = str(uuid4())
        card.source = owner
        cards.append(card)

    assert cards, "默认牌单为空：请检查 demo/card_prototypes.py 与 setup_demo 灌库"
    return cards


####################################################################################################################################
DECK_SIZE: Final[int] = 5  # 每副牌库固定 5 张


####################################################################################################################################
@prompt_builder
def _build_deck_select_prompt() -> str:
    """选型阶段提示词：只负责挑原型，具体设计交给卡牌设计世界实体。

    不重述身份：目标 actor 的 system prompt 由 card_common 的 actor 上下文入口作为数据块注入。
    """
    return f"""# 任务：为你自己组建初始牌库（恰好 {DECK_SIZE} 张）

依据上面给出的角色设定，从手牌原型库挑选恰好 {DECK_SIZE} 张组成初始牌库，使它们成为属于「你自己」的战斗资源，可重复选同一原型。先 `list_card_prototypes` 纵览，再对候选 `get_card_prototype` 精读，最后 `select_cards` 一次性提交恰好 {DECK_SIZE} 个 prototype_id。"""


####################################################################################################################################
@final
class AssembleDungeonDeckSystem(ReactiveProcessor):
    """为每个角色并发组建牌库。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(GenerateDungeonAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GenerateDungeonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 GenerateDungeonAction，数据异常"
        action = entities[0].get(GenerateDungeonAction)
        await self._run(
            deck_prototype_ids=list(action.spec.deck_prototype_ids) if action else []
        )

    ####################################################################################################################################
    async def _run(self, deck_prototype_ids: List[str]) -> None:
        draft: Optional[DungeonDraft] = self._game._dungeon_draft
        if draft is None or not draft.dungeon_name:
            logger.error("[AssembleDungeonDeckSystem] 中间过程数据缺失，跳过")
            return

        dungeon_name = draft.dungeon_name
        dungeon_path: Path = DUNGEONS_DIR / f"{dungeon_name}.json"
        if not dungeon_path.exists():
            logger.error(
                f"[AssembleDungeonDeckSystem] Dungeon 文件不存在: {dungeon_path}"
            )
            return

        try:
            dungeon = Dungeon.model_validate_json(
                dungeon_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            logger.error(
                f"[AssembleDungeonDeckSystem] 解析 Dungeon 失败: {e}\n路径: {dungeon_path}"
            )
            return

        combat_actors = [
            actor
            for room in dungeon.rooms
            if isinstance(room, CombatRoom)
            for actor in room.stage.actors
        ]

        logger.info(
            f"[AssembleDungeonDeckSystem] 开始: dungeon={dungeon_name}, actors={len(combat_actors)}"
        )

        # 预取一次手牌原型索引，供所有并发 agent_loop 共享（list_card_prototypes 返回缓存）
        index: List[CardPrototypeIndexEntry] = []
        try:
            index = list_card_prototype_index(card_type="手牌")
        except Exception as e:
            logger.error(
                f"[AssembleDungeonDeckSystem] 拉取卡牌原型索引失败，全部回退默认牌库: {e}"
            )

        # 如果存在战斗角色，则为每个角色组建牌库
        if combat_actors:
            tasks: List[Tuple[str, Coroutine[Any, Any, bool]]] = [
                (
                    actor.name,
                    self._assemble_actor_deck(actor, index, deck_prototype_ids),
                )
                for actor in combat_actors
            ]
            outcomes = await batch_run_boolean_tasks(tasks)
            succeeded = sum(1 for ok in outcomes if ok)
            logger.info(
                f"[AssembleDungeonDeckSystem] 牌库组建完成: {succeeded}/{len(combat_actors)} 个角色使用原型牌库"
            )

        # 写盘最终 Dungeon JSON（含已填充的牌库）
        dungeon_path.write_text(dungeon.model_dump_json(indent=4), encoding="utf-8")
        logger.info(
            f"[AssembleDungeonDeckSystem] Dungeon 已保存: {dungeon_path}\n  rooms ({len(dungeon.rooms)}): "
            + ", ".join(
                f"{room.stage.name}({room.stage.actors[0].name if room.stage.actors else 'no actor'})"
                for room in dungeon.rooms
            )
        )

    ####################################################################################################################################
    async def _assemble_actor_deck(
        self,
        actor: Actor,
        index: List[CardPrototypeIndexEntry],
        deck_prototype_ids: List[str],
    ) -> bool:
        """为单个角色组建并挂载牌库；返回 True 表示使用原型牌库，False 表示回退默认。"""
        try:
            # 尝试通过工具构建角色的牌库，返回牌列表和是否回退的标志
            cards, is_fallback = await self._build_cards(
                actor, index, deck_prototype_ids
            )

        except Exception as e:
            # 捕获组建牌库过程中出现的异常，记录错误并回退默认牌库
            logger.error(
                f"[AssembleDungeonDeckSystem] {actor.name} 牌库组建异常，回退默认: {e}"
            )
            cards = make_default_deck_cards(actor.name)
            is_fallback = True

        # 构建角色的牌库组件并挂载到角色身上（合并而非覆盖：MotifComponent 等要保留）
        deck = DeckComponent(name=actor.name, cards=cards)
        actor.components = {
            **actor.components,
            DeckComponent.__name__: deck.model_dump(),
        }
        return not is_fallback

    ####################################################################################################################################
    async def _build_cards(
        self,
        actor: Actor,
        index: List[CardPrototypeIndexEntry],
        deck_prototype_ids: List[str],
    ) -> Tuple[List[Card], bool]:
        """两阶段组建：怪物自选原型 → 卡牌设计世界实体设计；返回 (牌列表, 是否回退)。

        两阶段都用「世界.卡牌设计」作为宿主，上下文 = 世界契约（system）+ 怪物自己的
        system prompt（任务数据块）+ 艺术锚点（`MotifComponent.motif`，`profile` 同时生成），
        会话结束不留痕。

        `deck_prototype_ids` 非空时为**显式候选规格**（调测 / 脚本入口写入
        `GenerateDungeonAction.spec`）：跳过选型、按规格物化，牌库张数以规格为准
        （`DECK_SIZE` 只是「未指定规格」时默认路径的张数，不是约束）。
        """
        if not index:
            logger.warning(
                f"[AssembleDungeonDeckSystem] {actor.name} 原型索引为空，回退默认"
            )
            # 原型索引为空，无法进行选型，直接回退默认牌库
            return make_default_deck_cards(actor.name), True

        # 阶段一：选型。有显式规格就跳过 LLM 选型，否则让怪物自己挑。
        if deck_prototype_ids:
            # 显式规格：牌库张数以规格为准，直接使用这些原型 ID 作为选型结果
            logger.info(
                f"[AssembleDungeonDeckSystem] {actor.name} 使用显式候选规格（{len(deck_prototype_ids)} 张）: {deck_prototype_ids}"
            )
            selected = list(deck_prototype_ids)

        else:
            # 没有显式规格，使用 LLM 让怪物自己挑选原型
            selection = await select_prototypes_for_actor(
                self._game,
                actor_name=actor.name,
                actor_system_prompt=actor.system_message,
                index=index,
                size=DECK_SIZE,
                prompt=_build_deck_select_prompt(),
                max_rounds=12,
            )

            # 检查 LLM 选型结果是否为空，若为空则回退默认牌库
            if not selection:
                logger.warning(
                    f"[AssembleDungeonDeckSystem] {actor.name} 选型失败，回退默认"
                )
                return make_default_deck_cards(actor.name), True

            # LLM 选型成功，记录选中的原型 ID 列表
            selected = selection.selected

        # 物化选中原型为候选卡（同一原型可重复 → 各自独立 uuid、独立设计）
        candidates: List[Candidate] = []
        for prototype_id in selected:
            candidate = materialize_candidate(prototype_id, actor.name)
            if candidate is None:
                # 物化原型失败，直接回退默认牌库
                logger.error(
                    f"[AssembleDungeonDeckSystem] {actor.name} 物化原型 {prototype_id!r} 失败，回退默认"
                )
                return make_default_deck_cards(actor.name), True

            # 物化成功，将候选卡加入列表
            candidates.append(candidate)

        # 阶段二：设计。上下文口径同选型，另注入怪物自己的艺术锚点。
        outcome = await design_cards_for_actor(
            self._game,
            actor_name=actor.name,
            actor_system_prompt=actor.system_message,
            candidates=candidates,
            actor_motif=read_motif_from_components(actor.components),
            max_rounds=16,
        )

        # 检查设计阶段是否成功，若未全部完成则回退默认牌库
        if not outcome.ok or outcome.designed != len(candidates):
            logger.warning(
                f"[AssembleDungeonDeckSystem] {actor.name} 设计 {outcome.designed}/{len(candidates)} 未全部完成，回退默认"
            )
            return make_default_deck_cards(actor.name), True

        # 设计阶段成功，生成最终卡牌列表并返回
        cards: List[Card] = [candidate.card for candidate in candidates]
        logger.info(
            f"[AssembleDungeonDeckSystem] {actor.name} 组建原型牌库: "
            + ", ".join(c.name for c in cards)
        )

        # 返回最终生成的卡牌列表，标记为非回退默认牌库
        return cards, False
