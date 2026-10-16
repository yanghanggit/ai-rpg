"""副本牌库组建系统。"""

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
from pydantic import BaseModel

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    AFFIX_DESIGN_SPEC,
    BUILD_CARD_FIELD_DESCRIPTION,
    Actor,
    Card,
    ChatMessage,
    CombatRoom,
    DeckComponent,
    Dungeon,
    GenerateDungeonAction,
    NormalizedStrList,
    SystemMessage,
    apply_affix_design,
    apply_numeric_design,
    normalize_str_list,
    validate_affix_slot,
)
from ..models.dungeon_draft import DungeonDraft
from ..paths import DUNGEONS_DIR
from ..pgsql import (
    CardPrototypeIndexEntry,
    get_card_prototype,
    get_default_deck_card_jsons,
    list_card_prototype_index,
)
from ..utils import batch_run_boolean_tasks, prompt_builder

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
@final
class _DeckCardPick(BaseModel):
    """submit_deck_card 提交的单张卡牌选定（原型 id + 叙事改写 + 可选数值微调/词缀重设计）。"""

    prototype_id: str
    name: str
    description: str
    cost: Optional[int] = None
    damage: Optional[int] = None
    hit_count: Optional[int] = None
    block: Optional[int] = None
    on_play_affixes: Optional[NormalizedStrList] = None
    on_hit_affixes: Optional[NormalizedStrList] = None
    on_turn_end_affixes: Optional[NormalizedStrList] = None
    on_autonomous_affixes: Optional[NormalizedStrList] = None


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
        description="按 id 获取某个手牌卡牌原型的完整规格（name / summary / guide / card 全字段），用于精读候选。",
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
SUBMIT_DECK_CARD_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="submit_deck_card",
        description="选定一张卡牌原型并提交其设计（name / description，以及可选的词缀重设计）。每张卡各调用一次，用 prototype_id 精确指定原型。",
        parameters={
            "type": "object",
            "properties": {
                "prototype_id": {
                    "type": "string",
                    "description": "所选原型的 id，必须来自 list_card_prototypes 返回的索引",
                },
                "name": {
                    "type": "string",
                    "description": "设计后的卡牌名（叙事、有辨识度，避免教学性命名的原型名）",
                },
                "description": {
                    "type": "string",
                    "description": "设计后的叙事描述（叙事锚点：不含数值，不重述字段已确定的效果）",
                },
                "cost": {
                    "type": "integer",
                    "description": "可选：在原型基础上微调本卡 cost；不给则沿用原型。",
                },
                "damage": {
                    "type": "integer",
                    "description": "可选：在原型基础上微调本卡 damage；不给则沿用原型。",
                },
                "hit_count": {
                    "type": "integer",
                    "description": "可选：在原型基础上微调本卡 hit_count（攻击次数）；不给则沿用原型。",
                },
                "block": {
                    "type": "integer",
                    "description": "可选：在原型基础上微调本卡 block（持有期格挡）；不给则沿用原型。",
                },
                "on_play_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 3,
                    "description": "本卡打出时结算的即时词缀（可选，多值列表）：每个元素是一条完整独立词缀，格式 `[词缀名]:机械结算描述`；禁止把一条词缀拆成多个元素或把多条合并进一个元素；无则 []。仅当原型该槽非空（有引导）时可提交；须满足词缀格式，否则整槽置空。",
                },
                "on_hit_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 3,
                    "description": "本卡持有者被命中时触发的受击词缀（可选，多值列表）：每个元素是一条完整独立词缀，格式同上；禁止拆分或合并；无则 []。仅当原型该槽非空时可提交。",
                },
                "on_turn_end_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 3,
                    "description": "持有者每次 pass turn 结算的回合结束词缀（可选，多值列表）：每个元素是一条完整独立词缀，格式同上；禁止拆分或合并；无则 []。仅当原型该槽非空时可提交。",
                },
                "on_autonomous_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 3,
                    "description": "卡牌自主运行词缀（可选，多值列表）：持有者每次 pass turn（回合结束词缀之后）结算，效果目标可为场上任意存活角色（敌人/友方/持有者，由词缀文本决定），不锁定持有者；格式同上；无则 []。仅当原型该槽非空时可提交。",
                },
            },
            "required": ["prototype_id", "name", "description"],
            "additionalProperties": False,
        },
    )
)


####################################################################################################################################
FINISH_DECK_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="finish_deck",
        description=f"所有卡牌均已通过 submit_deck_card 提交后调用，结束本次牌库组建。",
        parameters={"type": "object", "properties": {}},
    )
)


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
        f"[AssembleDeckSystem] list_card_prototypes 执行: 共 {len(payload)} 个手牌原型"
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
    logger.info(f"[AssembleDeckSystem] get_card_prototype 执行: {prototype_id}")
    return json.dumps(
        {
            "id": proto.prototype_id,
            "name": proto.name,
            "summary": proto.summary,
            "keywords": json.loads(proto.keywords_json),
            "guide": proto.guide,
            "card": json.loads(proto.card_json),
        },
        ensure_ascii=False,
    )


####################################################################################################################################
def _handle_submit_deck_card(
    valid_ids: Set[str],
    prototype_cards: Dict[str, Card],
    picks: List[_DeckCardPick],
    prototype_id: str,
    name: str,
    description: str,
    cost: Optional[int] = None,
    damage: Optional[int] = None,
    hit_count: Optional[int] = None,
    block: Optional[int] = None,
    on_play_affixes: Optional[NormalizedStrList] = None,
    on_hit_affixes: Optional[NormalizedStrList] = None,
    on_turn_end_affixes: Optional[NormalizedStrList] = None,
    on_autonomous_affixes: Optional[NormalizedStrList] = None,
    **ignored: Any,
) -> str:
    """处理 submit_deck_card：校验原型 id 与词缀，不合法则返回错误让 agent 修正重提。

    原型中只读的布尔/目标字段（target_type/playable/exhaust/retain/
    ethereal/transferable）有时会被模型一并回传，这里统一忽略，避免因多余参数报错。
    """
    if ignored:
        logger.info(
            f"[AssembleDeckSystem] submit_deck_card 忽略只读字段: {sorted(ignored)}"
        )
    assert name.strip(), "name 不能为空"
    assert description.strip(), "description 不能为空"
    if prototype_id not in valid_ids:
        return (
            f"错误：未知原型 id {prototype_id!r}。"
            "可用 id 请通过 list_card_prototypes 查询。"
        )

    card = prototype_cards.get(prototype_id)
    if card is not None:
        problems: List[str] = []

        # 校验提交的词缀是否合法
        for field, submitted in (
            ("on_play_affixes", on_play_affixes),
            ("on_hit_affixes", on_hit_affixes),
            ("on_turn_end_affixes", on_turn_end_affixes),
            ("on_autonomous_affixes", on_autonomous_affixes),
        ):
            items = normalize_str_list(submitted or [])

            # 如果原型该槽位为空，则不允许提交任何词缀
            if not getattr(card, field):

                # 如果原型该槽位为空，但提交了词缀，则记录问题
                if items:
                    problems.append(f"{field} 不可设计（原型该槽无引导），请勿提交")

                continue

            # 校验每个提交的词缀是否合法
            for affix in items:
                result = validate_affix_slot(field, affix, card)
                if not result.ok:
                    problems.append(f"{field}: {affix!r} → {result.reason}")

        if problems:
            detail = "\n".join(f"- {p}" for p in problems)
            return (
                "错误：词缀不合法，本卡未记录。请修正后重新调用 submit_deck_card：\n"
                + detail
            )

    picks.append(
        _DeckCardPick(
            prototype_id=prototype_id,
            name=name.strip(),
            description=description.strip(),
            cost=cost,
            damage=damage,
            hit_count=hit_count,
            block=block,
            on_play_affixes=on_play_affixes,
            on_hit_affixes=on_hit_affixes,
            on_turn_end_affixes=on_turn_end_affixes,
            on_autonomous_affixes=on_autonomous_affixes,
        )
    )
    logger.info(
        f"[AssembleDeckSystem] submit_deck_card: {prototype_id} → {name} "
        f"（已选 {len(picks)}/{DECK_SIZE}）"
    )
    return f"已记录第 {len(picks)} 张卡牌。"


####################################################################################################################################
def _handle_finish_deck() -> str:
    """处理 finish_deck 工具调用（无参，仅作为终止信号）。"""
    return "已结束牌库组建。"


####################################################################################################################################
@prompt_builder
def _build_deck_prompt(actor_name: str) -> str:
    """生成组建初始牌库（选 5 张原型 + 设计 name/description/词缀）提示词。"""
    return f"""# 任务：为你自己组建初始牌库（恰好 {DECK_SIZE} 张）

你是「{actor_name}」。请依据角色设定（见对话开头的系统设定），从卡牌原型库挑选恰好 {DECK_SIZE} 张组成初始牌库，并逐张设计，使其成为「你自己」的招式、习惯或随身手段。

{BUILD_CARD_FIELD_DESCRIPTION}

{AFFIX_DESIGN_SPEC}

## 原型与设计边界

- **布尔与目标字段只读**：`target_type/playable/exhaust/retain/ethereal/transferable` 由原型给定，不可改动。
- **数值可微调**：`cost/damage/hit_count/block` 可在原型基础上调整（提交时可选给出，不给则沿用原型）。
- **只能对** `get_card_prototype` 返回的 `card` 中已非空（有引导）的词缀槽提交设计；其余槽位不得新增，不提交或设计不合法则该槽置空。
- **你来设计**：`name`、`description`（叙事表达，不重述数值与机械效果；可自由采用动作 / 物件 / 意象 / 氛围 / 典故等形态），以及上述槽位内的词缀全文。
- 可重复选同一原型（得到多张独立卡牌），但总数必须恰好 {DECK_SIZE} 张。

## 工作流程

1. `list_card_prototypes` 纵览全部手牌原型（archetype / subtype / summary / keywords），结合角色设定筛选方向；
2. 对候选调用 `get_card_prototype` 精读（guide + card 全字段）；
3. 对选定的 {DECK_SIZE} 张各调用一次 `submit_deck_card`：给出 `prototype_id` / `name` / `description`，按需微调数值，并对原型已存在的槽位提交你重设计的词缀（格式与约束见上「词缀设计规范」）；
4. 全部提交后调用 `finish_deck` 结束。"""


####################################################################################################################################
@final
class AssembleDeckSystem(ReactiveProcessor):
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
            logger.error("[AssembleDeckSystem] 中间过程数据缺失，跳过")
            return

        dungeon_name = draft.dungeon_name
        dungeon_path: Path = DUNGEONS_DIR / f"{dungeon_name}.json"
        if not dungeon_path.exists():
            logger.error(f"[AssembleDeckSystem] Dungeon 文件不存在: {dungeon_path}")
            return

        try:
            dungeon = Dungeon.model_validate_json(
                dungeon_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            logger.error(
                f"[AssembleDeckSystem] 解析 Dungeon 失败: {e}\n路径: {dungeon_path}"
            )
            return

        combat_actors = [
            actor
            for room in dungeon.rooms
            if isinstance(room, CombatRoom)
            for actor in room.stage.actors
        ]

        logger.info(
            f"[AssembleDeckSystem] 开始: dungeon={dungeon_name}, "
            f"actors={len(combat_actors)}"
        )

        # 预取一次手牌原型索引，供所有并发 agent_loop 共享（list_card_prototypes 返回缓存）
        index: List[CardPrototypeIndexEntry] = []
        try:
            index = list_card_prototype_index(card_type="手牌")
        except Exception as e:
            logger.error(
                f"[AssembleDeckSystem] 拉取卡牌原型索引失败，全部回退默认牌库: {e}"
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
                f"[AssembleDeckSystem] 牌库组建完成: "
                f"{succeeded}/{len(combat_actors)} 个角色使用原型牌库"
            )

        # 写盘最终 Dungeon JSON（含已填充的牌库）
        dungeon_path.write_text(dungeon.model_dump_json(indent=4), encoding="utf-8")
        logger.info(
            f"[AssembleDeckSystem] Dungeon 已保存: {dungeon_path}\n"
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
                f"[AssembleDeckSystem] {actor.name} 牌库组建异常，回退默认: {e}"
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
        """让 actor 通过工具自选 5 张原型并润色；返回 (牌列表, 是否回退)。"""
        if not index:
            logger.warning(f"[AssembleDeckSystem] {actor.name} 原型索引为空，回退默认")
            return make_default_deck_cards(actor.name), True

        picks: List[_DeckCardPick] = []
        valid_ids: Set[str] = {item["prototype_id"] for item in index}
        prototype_cards: Dict[str, Card] = {}
        for pid in valid_ids:
            try:
                prototype_cards[pid] = Card.model_validate(
                    json.loads(get_card_prototype(pid).card_json)
                )
            except Exception as e:
                logger.error(f"[AssembleDeckSystem] 预取原型 {pid} 失败: {e}")

        # 上下文隔离：以 actor 自己的 system_message 为唯一上下文，
        # 传入全新列表（agent_loop 原地追加），结束后丢弃 → 选完自动「失忆」。
        messages: List[ChatMessage] = [SystemMessage(content=actor.system_message)]

        try:
            ok = await agent_loop(
                name=actor.name,
                input_message=_build_deck_prompt(actor.name),
                messages=messages,
                tools=[
                    LIST_CARD_PROTOTYPES_TOOL,
                    GET_CARD_PROTOTYPE_TOOL,
                    SUBMIT_DECK_CARD_TOOL,
                    FINISH_DECK_TOOL,
                ],
                handlers={
                    LIST_CARD_PROTOTYPES_TOOL.function.name: partial(
                        _handle_list_card_prototypes, index
                    ),
                    GET_CARD_PROTOTYPE_TOOL.function.name: _handle_get_card_prototype,
                    SUBMIT_DECK_CARD_TOOL.function.name: partial(
                        _handle_submit_deck_card, valid_ids, prototype_cards, picks
                    ),
                    FINISH_DECK_TOOL.function.name: _handle_finish_deck,
                },
                max_rounds=16,
                terminal_tools=[FINISH_DECK_TOOL],
            )
        except Exception as e:
            logger.error(f"[AssembleDeckSystem] {actor.name} agent_loop 异常: {e}")
            return make_default_deck_cards(actor.name), True

        if not ok:
            logger.warning(
                f"[AssembleDeckSystem] {actor.name} agent_loop 失败，回退默认"
            )
            return make_default_deck_cards(actor.name), True

        if len(picks) != DECK_SIZE:
            logger.warning(
                f"[AssembleDeckSystem] {actor.name} 提交 {len(picks)} 张卡牌"
                f"（需 {DECK_SIZE}），回退默认"
            )
            return make_default_deck_cards(actor.name), True

        cards: List[Card] = []
        try:

            # 遍历每个提交的卡牌，物化为最终的 Card 对象
            for pick in picks:
                proto = get_card_prototype(pick.prototype_id)
                if proto.card_type != "手牌":
                    raise ValueError(
                        f"原型 {pick.prototype_id!r} 不是手牌原型"
                        f"（card_type={proto.card_type!r}）"
                    )
                card = Card.model_validate(json.loads(proto.card_json))
                # 原型 uuid 是共享常量，必须换新；source 回填持有者名（牌库入口不变量）
                card.uuid = str(uuid4())
                card.source = actor.name
                card.name = pick.name
                card.description = pick.description

                # 骨架数值微调（不加护栏；None 表示沿用原型）
                apply_numeric_design(
                    card,
                    cost=pick.cost,
                    damage=pick.damage,
                    hit_count=pick.hit_count,
                    block=pick.block,
                )

                # 词缀：在原型引导下重设计；不合法则整槽置空
                _, notes = apply_affix_design(
                    actor.name,
                    card,
                    {
                        "on_play_affixes": pick.on_play_affixes,
                        "on_hit_affixes": pick.on_hit_affixes,
                        "on_turn_end_affixes": pick.on_turn_end_affixes,
                        "on_autonomous_affixes": pick.on_autonomous_affixes,
                    },
                )

                # 记录词缀设计过程中的警告信息
                for note in notes:
                    logger.warning(f"[AssembleDeckSystem] {note}")

                # 将处理完的卡牌加入最终牌库
                cards.append(card)

        except Exception as e:

            # 物化卡牌失败，回退默认牌库
            logger.error(f"[AssembleDeckSystem] {actor.name} 物化卡牌失败: {e}")
            return make_default_deck_cards(actor.name), True

        logger.info(
            f"[AssembleDeckSystem] {actor.name} 组建原型牌库: "
            + ", ".join(c.name for c in cards)
        )
        return cards, False
