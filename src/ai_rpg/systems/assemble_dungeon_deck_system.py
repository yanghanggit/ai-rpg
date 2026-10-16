"""副本怪物牌库组建系统（地下城生成管线：为每个战斗房间的怪物从卡牌原型库组建并润色牌库）。

牌库组建分两阶段，都以怪物自己的 system prompt 作为**唯一且临时**的上下文
（`agent_loop` 结束后即丢弃，不写回持久记忆）：

1. 选型：怪物浏览手牌原型库，用 `select_deck_cards` 一次性提交恰好 DECK_SIZE 个 id；
2. 设计：由 `card_design` 引擎把选中原型物化为候选卡，交给同一怪物完成
   name / description / 数值微调与词缀设计。

设计契约（工具、词缀校验、落地）统一由 `card_design` 提供；本系统只负责「选型 + 组装」，
不再自带设计逻辑，也不再注入全局字段 / 词缀规范。
"""

import json
from functools import partial
from pathlib import Path
from typing import (
    Any,
    Coroutine,
    Dict,
    Final,
    List,
    Optional,
    Set,
    Tuple,
    final,
    override,
)
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, Field

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
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
    SystemMessage,
)
from ..paths import DUNGEONS_DIR
from ..pgsql import (
    CardPrototypeIndexEntry,
    get_card_prototype,
    get_default_deck_card_jsons,
    list_card_prototype_index,
)
from ..utils import batch_run_boolean_tasks, prompt_builder
from .card_design import Candidate, materialize_candidate, run_card_design_session


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
LIST_CARD_PROTOTYPES_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="list_card_prototypes",
        description="纵览全部可选手牌卡牌原型的索引（id / archetype / archetype_subtype / name / summary / keywords），用于组建牌库前建立全局观。",
        parameters={"type": "object", "properties": {}},
    )
)


####################################################################################################################################
GET_CARD_PROTOTYPE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="get_card_prototype",
        description="按 id 获取某个手牌卡牌原型的完整规格（name / summary / design / card 全字段），用于精读候选。",
        parameters={
            "type": "object",
            "properties": {
                "prototype_id": {
                    "type": "string",
                    "description": "原型 id，必须来自 list_card_prototypes 返回的索引（如 proto.attack / proto.burst）",
                },
            },
            "required": ["prototype_id"],
        },
    )
)


####################################################################################################################################
SELECT_DECK_CARDS_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="select_deck_cards",
        description=f"一次性提交恰好 {DECK_SIZE} 个手牌原型 id（可重复），确定初始牌库的原型组成，随后进入逐张设计。",
        parameters={
            "type": "object",
            "properties": {
                "prototype_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": DECK_SIZE,
                    "maxItems": DECK_SIZE,
                    "description": f"恰好 {DECK_SIZE} 个原型 id，必须来自 list_card_prototypes 返回的索引，可重复",
                },
            },
            "required": ["prototype_ids"],
        },
    )
)


####################################################################################################################################
@final
class _DeckSelection(BaseModel):
    """select_deck_cards 的结果容器：怪物选定的原型 id 列表（可重复）。"""

    prototype_ids: List[str] = Field(default_factory=list)


####################################################################################################################################
def _handle_list_card_prototypes(index: List[CardPrototypeIndexEntry]) -> str:
    """处理 list_card_prototypes 工具调用：返回缓存的手牌原型索引纵览。"""
    payload = [
        {
            "id": item["prototype_id"],
            "archetype": item["archetype"],
            "archetype_subtype": item["archetype_subtype"],
            "name": item["name"],
            "summary": item["summary"],
            "keywords": item["keywords"],
        }
        for item in index
    ]
    logger.info(
        f"[AssembleDungeonDeckSystem] list_card_prototypes 执行: 共 {len(payload)} 个手牌原型"
    )
    return json.dumps(payload, ensure_ascii=False)


####################################################################################################################################
def _handle_get_card_prototype(prototype_id: str) -> str:
    """处理 get_card_prototype 工具调用：按 id 返回完整卡牌原型（含 card 全字段）。"""
    try:

        # 尝试获取卡牌原型，如果不存在则抛出 ValueError
        proto = get_card_prototype(prototype_id)
    except ValueError as e:

        # 获取卡牌原型失败，返回错误信息
        return f"错误：{e}。可用 id 请通过 list_card_prototypes 查询。"

    # 校验卡牌类型是否为手牌，非手牌则返回错误信息
    if proto.card_type != "手牌":
        return f"错误：{prototype_id!r} 不是手牌卡牌原型，可用 id 请通过 list_card_prototypes 查询。"

    # 返回卡牌原型的完整信息（含 card 全字段）
    logger.info(f"[AssembleDungeonDeckSystem] get_card_prototype 执行: {prototype_id}")
    return json.dumps(
        {
            "id": proto.prototype_id,
            "name": proto.name,
            "summary": proto.summary,
            "keywords": json.loads(proto.keywords_json),
            "design": proto.design,
            "card": json.loads(proto.card_json),
        },
        ensure_ascii=False,
    )


####################################################################################################################################
def _handle_select_deck_cards(
    selection: _DeckSelection,
    valid_ids: Set[str],
    prototype_ids: List[str],
) -> str:
    """处理 select_deck_cards：校验数量与 id 合法性，不合法则返回错误让 agent 修正重提。"""
    if len(prototype_ids) != DECK_SIZE:
        return (
            f"错误：需恰好 {DECK_SIZE} 个 prototype_id，实际 {len(prototype_ids)}。"
            "请修正后重新调用 select_deck_cards。"
        )

    unknown = [pid for pid in prototype_ids if pid not in valid_ids]
    if unknown:
        return (
            f"错误：未知原型 id {unknown}。"
            "可用 id 请通过 list_card_prototypes 查询。"
        )

    selection.prototype_ids = list(prototype_ids)
    logger.info(
        f"[AssembleDungeonDeckSystem] select_deck_cards: {selection.prototype_ids}"
    )
    return f"已记录 {len(selection.prototype_ids)} 张牌的原型选择。"


####################################################################################################################################
@prompt_builder
def _build_deck_select_prompt(actor_name: str) -> str:
    """选型阶段提示词：只负责挑原型，具体设计交给 card_design 引擎。"""
    return f"""# 任务：为你自己组建初始牌库（恰好 {DECK_SIZE} 张）

你是「{actor_name}」。依据角色设定（见系统提示），从手牌原型库挑选恰好 {DECK_SIZE} 张组成初始牌库，使它们成为「你自己」的招式、习惯或随身手段。可重复选同一原型。

工作流程：
1. `list_card_prototypes` 纵览全部手牌原型（archetype / subtype / summary / keywords）；
2. 对候选调用 `get_card_prototype` 精读（design + card 全字段）；
3. `select_deck_cards` 一次性提交恰好 {DECK_SIZE} 个 prototype_id。"""


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
        await self._run()

    ####################################################################################################################################
    async def _run(self) -> None:
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
            f"[AssembleDungeonDeckSystem] 开始: dungeon={dungeon_name}, "
            f"actors={len(combat_actors)}"
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
                (actor.name, self._assemble_actor_deck(actor, index))
                for actor in combat_actors
            ]
            outcomes = await batch_run_boolean_tasks(tasks)
            succeeded = sum(1 for ok in outcomes if ok)
            logger.info(
                f"[AssembleDungeonDeckSystem] 牌库组建完成: "
                f"{succeeded}/{len(combat_actors)} 个角色使用原型牌库"
            )

        # 写盘最终 Dungeon JSON（含已填充的牌库）
        dungeon_path.write_text(dungeon.model_dump_json(indent=4), encoding="utf-8")
        logger.info(
            f"[AssembleDungeonDeckSystem] Dungeon 已保存: {dungeon_path}\n"
            f"  rooms ({len(dungeon.rooms)}): "
            + ", ".join(
                f"{room.stage.name}({room.stage.actors[0].name if room.stage.actors else 'no actor'})"
                for room in dungeon.rooms
            )
        )

    ####################################################################################################################################
    async def _assemble_actor_deck(
        self, actor: Actor, index: List[CardPrototypeIndexEntry]
    ) -> bool:
        """为单个角色组建并挂载牌库；返回 True 表示使用原型牌库，False 表示回退默认。"""
        try:
            # 尝试通过工具构建角色的牌库，返回牌列表和是否回退的标志
            cards, is_fallback = await self._build_cards(actor, index)

        except Exception as e:
            # 捕获组建牌库过程中出现的异常，记录错误并回退默认牌库
            logger.error(
                f"[AssembleDungeonDeckSystem] {actor.name} 牌库组建异常，回退默认: {e}"
            )
            cards = make_default_deck_cards(actor.name)
            is_fallback = True

        # 构建角色的牌库组件并挂载到角色身上
        deck = DeckComponent(name=actor.name, cards=cards)
        actor.components = {DeckComponent.__name__: deck.model_dump()}
        return not is_fallback

    ####################################################################################################################################
    async def _build_cards(
        self, actor: Actor, index: List[CardPrototypeIndexEntry]
    ) -> Tuple[List[Card], bool]:
        """两阶段组建：怪物自选原型 → card_design 引擎设计；返回 (牌列表, 是否回退)。

        两阶段都以怪物自己的 system prompt 作为唯一且临时的上下文。
        """
        if not index:
            logger.warning(
                f"[AssembleDungeonDeckSystem] {actor.name} 原型索引为空，回退默认"
            )
            return make_default_deck_cards(actor.name), True

        valid_ids: Set[str] = {item["prototype_id"] for item in index}
        selection = _DeckSelection()

        # 阶段一：选型。怪物自己的 system prompt 作为唯一上下文，结束后丢弃。
        try:
            picked = await agent_loop(
                name=actor.name,
                input_message=_build_deck_select_prompt(actor.name),
                messages=[SystemMessage(content=actor.system_message)],
                tools=[
                    LIST_CARD_PROTOTYPES_TOOL,
                    GET_CARD_PROTOTYPE_TOOL,
                    SELECT_DECK_CARDS_TOOL,
                ],
                handlers={
                    LIST_CARD_PROTOTYPES_TOOL.function.name: partial(
                        _handle_list_card_prototypes, index
                    ),
                    GET_CARD_PROTOTYPE_TOOL.function.name: _handle_get_card_prototype,
                    SELECT_DECK_CARDS_TOOL.function.name: partial(
                        _handle_select_deck_cards, selection, valid_ids
                    ),
                },
                max_rounds=12,
                terminal_tools=[SELECT_DECK_CARDS_TOOL],
            )
        except Exception as e:
            logger.error(
                f"[AssembleDungeonDeckSystem] {actor.name} 选型 agent_loop 异常: {e}"
            )
            return make_default_deck_cards(actor.name), True

        if not picked or len(selection.prototype_ids) != DECK_SIZE:
            logger.warning(
                f"[AssembleDungeonDeckSystem] {actor.name} 选型失败"
                f"（{len(selection.prototype_ids)}/{DECK_SIZE}），回退默认"
            )
            return make_default_deck_cards(actor.name), True

        # 物化选中原型为候选卡（同一原型可重复 → 各自独立 uuid、独立设计）
        candidates: List[Candidate] = []
        for prototype_id in selection.prototype_ids:
            candidate = materialize_candidate(prototype_id, actor.name)
            if candidate is None:
                logger.error(
                    f"[AssembleDungeonDeckSystem] {actor.name} 物化原型 "
                    f"{prototype_id!r} 失败，回退默认"
                )
                return make_default_deck_cards(actor.name), True
            candidates.append(candidate)

        # 阶段二：设计。同样以怪物自己的 system prompt 作为唯一临时上下文。
        outcome = await run_card_design_session(
            actor.name,
            candidates,
            [SystemMessage(content=actor.system_message)],
            max_rounds=16,
        )
        if not outcome.ok or outcome.designed != DECK_SIZE:
            logger.warning(
                f"[AssembleDungeonDeckSystem] {actor.name} 设计 "
                f"{outcome.designed}/{DECK_SIZE} 未全部完成，回退默认"
            )
            return make_default_deck_cards(actor.name), True

        cards: List[Card] = [candidate.card for candidate in candidates]
        logger.info(
            f"[AssembleDungeonDeckSystem] {actor.name} 组建原型牌库: "
            + ", ".join(c.name for c in cards)
        )
        return cards, False
