"""战斗房间本地调试用固定 Mock 数据。

服务器尚未启动时（`--dev-screen combat-room` 跳过登录，`session is None`），
`CombatInitScreen` 使用本模块构造的固定 2v2（玩家+队友 vs 怪物x2）数据，
数据形状与真实服务端响应（DungeonRoomResponse / StagesStateResponse /
EntitiesDetailsResponse）严格一致，均通过真实 Pydantic 模型构造而非裸 dict，
保证 schema 变化时能第一时间在此处报错。
"""

from typing import Dict, Final, List, Optional, Tuple

from ..models import (
    Actor as DungeonActor,
)
from ..models import (
    ActorComponent,
    ActorType,
    AnyItem,
    AppearanceComponent,
    Card,
    CharacterStats,
    CharacterStatsComponent,
    Combat,
    CombatLootComponent,
    CombatResult,
    CombatRoom,
    CombatState,
    ComponentSerialization,
    ConsumableItem,
    CostumeItem,
    DeckComponent,
    DiscardPileComponent,
    DrawPileComponent,
    Dungeon,
    DungeonComponent,
    DungeonRoomResponse,
    DungeonStateResponse,
    EntitiesDetailsResponse,
    EntitySerialization,
    ExhaustPileComponent,
    GearItem,
    GeneratedImage,
    HandComponent,
    IdentityComponent,
    InventoryComponent,
    MaterialItem,
    MonsterComponent,
    NPCComponent,
    PartyMemberComponent,
    PlayerComponent,
    Round,
    RoundStatsComponent,
    StageComponent,
    StagesStateResponse,
    StageType,
    StorageComponent,
    WornCostumeComponent,
)
from ..models import (
    Stage as DungeonStage,
)

# ── 固定身份信息（session is None 时使用，替代真实登录会话）──
MOCK_USER_NAME: Final[str] = "mock_user"
MOCK_GAME_NAME: Final[str] = "mock_game"
MOCK_ACTOR_NAME: Final[str] = "艾伦"

MOCK_STAGE_NAME: Final[str] = "回廊-副本"
MOCK_TEAMMATE_NAME: Final[str] = "赛琳"
MOCK_MONSTER_1_NAME: Final[str] = "哥布林-甲"
MOCK_MONSTER_2_NAME: Final[str] = "哥布林-乙"

MOCK_STORAGE_NAME: Final[str] = (
    "全局储物箱"  # mock 模式下储物箱实体名（resolve_storage_entity / get_storage_component 固定替代）
)

MOCK_COMBAT_NAME: Final[str] = f"{MOCK_STAGE_NAME}-combat"

MOCK_DUNGEON_NAME: Final[str] = "回廊副本"
MOCK_NEXT_STAGE_NAME: Final[str] = "回廊-副本-次关"

# ── 可变 mock 战斗状态（仅开发调试用：模拟服务端状态推进，例如确认开始战斗后置为 ONGOING）──
_mock_combat_state: CombatState = CombatState.INITIALIZATION

# ── 可变 mock 战斗结果（仅开发调试用：POST_COMBAT 结算态下展示胜负结果）──
_mock_combat_result: CombatResult = CombatResult.NONE

# ── 可变 mock 战斗回合列表（仅开发调试用：模拟 CombatRoundStartSystem 创建的新回合，
# 作为 build_mock_dungeon_room_response 中 combat.rounds 的唯一数据源）──
_mock_rounds: List[Round] = []

# ── 可变 mock 副本房间索引（仅开发调试用：模拟"进入下一关"后 current_room_index 前进）──
_mock_current_room_index: int = 0

# ── 可变 mock 背包 / 战利品（仅开发调试用：模拟 collect_loot 把战利品转入背包）──
_mock_inventory_items: List[AnyItem] = [
    ConsumableItem(name="治疗药水", description="恢复少量生命值。"),
    ConsumableItem(name="力量药剂", description="短暂提升攻击力。"),
    GearItem(
        name="淬炼长剑",
        description="一把普通但锐利的长剑，适合新手冒险者。",
        cards=[
            Card(
                name="淬炼长剑",
                description="一把普通但锐利的长剑，适合新手冒险者。",
                cost=1,
                damage=5,
            ),
        ],
    ),
]

_mock_loot_items: List[AnyItem] = [
    MaterialItem(name="哥布林牙", description="哥布林掉落的牙齿，可用于合成。"),
    MaterialItem(name="哥布林皮", description="哥布林掉落的皮革，可用于合成。"),
]

# ── 可变 mock 时装穿戴状态（仅开发调试用：模拟「穿戴时装」指令的储物箱 ⇄ 已穿戴状态转移，
# 初始值与「艾伦已穿戴旅者披风 / 储物箱持有学者长袍与沙丘游侠斗篷」这一固定叙事保持一致）──
_mock_worn_costume_by_actor: Dict[str, CostumeItem] = {
    MOCK_ACTOR_NAME: CostumeItem(
        name="旅者披风",
        description="一件轻便的深绿色披风，边缘绣有简单的藤蔓纹样。",
    ),
}
_mock_storage_costume_items: List[CostumeItem] = [
    CostumeItem(
        name="学者长袍",
        description="一件朴素的深色长袍，袖口绣有简单的符文纹样。",
    ),
    CostumeItem(
        name="沙丘游侠斗篷",
        description="沙黄色的轻便斗篷，兜帽边缘镶有防风布条。",
    ),
]


def get_mock_worn_costume(actor_name: str) -> Optional[CostumeItem]:
    return _mock_worn_costume_by_actor.get(actor_name)


def get_mock_storage_costume_items() -> List[CostumeItem]:
    return list(_mock_storage_costume_items)


def get_mock_storage_component() -> StorageComponent:
    """构造 mock 全局储物箱的 StorageComponent（名称 + 全部道具）。"""
    return StorageComponent(
        name=MOCK_STORAGE_NAME,
        items=[
            *get_mock_storage_costume_items(),
            MaterialItem(
                name="哥布林牙",
                description="哥布林掉落的牙齿，可用于合成。",
            ),
        ],
    )


def simulate_mock_wear_costume(actor_name: str, item_name: str) -> None:
    """开发调试用：模拟 activate_wear_costume → WearCostumeActionSystem
    的核心状态转移（若已穿戴则先自动脱装归还储物箱 → 从储物箱取出指定时装并穿装），
    不做真实 LLM 外观合成，直接同步生效，供 `--dev-screen wear-costume` 下完整走通
    穿戴/换装流程。

    Raises:
        ValueError: 储物箱中不存在同名时装。
    """
    current = _mock_worn_costume_by_actor.pop(actor_name, None)
    if current is not None:
        _mock_storage_costume_items.append(current)

    match = next(
        (item for item in _mock_storage_costume_items if item.name == item_name), None
    )
    if match is None:
        raise ValueError(f"（mock）储物箱中不存在名为 {item_name!r} 的时装")

    _mock_storage_costume_items.remove(match)
    _mock_worn_costume_by_actor[actor_name] = match


def simulate_mock_remove_costume(actor_name: str) -> None:
    """开发调试用：模拟 activate_remove_costume → RemoveCostumeActionSystem
    的核心状态转移（脱装归还储物箱），无穿戴时装则静默跳过。
    """
    current = _mock_worn_costume_by_actor.pop(actor_name, None)
    if current is not None:
        _mock_storage_costume_items.append(current)


def set_mock_combat_state(state: CombatState) -> None:
    """开发调试用：切换 mock 战斗状态（如确认开始战斗后置为 ONGOING）。"""
    global _mock_combat_state
    _mock_combat_state = state


def get_mock_combat_state() -> CombatState:
    return _mock_combat_state


def set_mock_combat_result(result: CombatResult) -> None:
    """开发调试用：切换 mock 战斗结果（如 POST_COMBAT 结算态下置为 WIN）。"""
    global _mock_combat_result
    _mock_combat_result = result


def get_mock_combat_result() -> CombatResult:
    return _mock_combat_result


def set_mock_current_room_index(index: int) -> None:
    """开发调试用：切换 mock 副本当前房间索引（如"进入下一关"成功后前进）。"""
    global _mock_current_room_index
    _mock_current_room_index = index


def get_mock_current_room_index() -> int:
    return _mock_current_room_index


def reset_mock_combat_rounds() -> None:
    """开发调试用：清空 mock 战斗回合（进入 ONGOING 但尚未开新回合时调用）。"""
    _mock_rounds.clear()


def simulate_mock_draw_cards() -> Tuple[bool, str]:
    """开发调试用：模拟 `/draw`（DrawCardsAction → CombatRoundStartSystem 创建
    新回合 + DrawCardsActionSystem 填手牌并置 draw_completed）。"""
    if _mock_combat_state != CombatState.ONGOING:
        return False, "[yellow]当前战斗未在 ONGOING 状态，无法抓牌。[/]"

    latest = _mock_rounds[-1] if _mock_rounds else None
    if latest is not None and not latest.is_completed and latest.draw_completed:
        return False, "[yellow]本回合已抽牌，无法重复抽牌。[/]"

    _mock_rounds.append(
        Round(
            completed_actors=[],
            action_order=[
                MOCK_ACTOR_NAME,
                MOCK_TEAMMATE_NAME,
                MOCK_MONSTER_1_NAME,
                MOCK_MONSTER_2_NAME,
            ],
            current_actor=MOCK_ACTOR_NAME,
            is_completed=False,
            draw_completed=True,
        )
    )
    return True, (
        f"[bold green]✅ 已开新回合并抓牌完成（第 {len(_mock_rounds)} 回合）。[/]"
    )


def _mock_current_round() -> Optional[Round]:
    return _mock_rounds[-1] if _mock_rounds else None


def _mock_validate_turn() -> Tuple[bool, str, Optional[Round]]:
    """校验 mock 回合行动前置条件，返回 (是否可行动, 错误文本, 当前回合)。"""
    if _mock_combat_state != CombatState.ONGOING:
        return False, "[yellow]当前战斗未在 ONGOING 状态，无法行动。[/]", None
    latest = _mock_current_round()
    if latest is None:
        return False, "[yellow]当前没有进行中的回合。[/]", None
    if latest.is_completed:
        return False, "[yellow]本回合已完成。[/]", None
    if not latest.draw_completed:
        return False, "[yellow]本回合尚未抓牌。[/]", None
    if latest.current_actor is None:
        return False, "[yellow]当前没有行动角色。[/]", None
    return True, "", latest


def _mock_advance_turn(latest: Round) -> Optional[str]:
    """把 current_actor 追加进 completed_actors，并推进到下一个未行动角色；
    全员过完则置 is_completed。返回下一个行动角色名（无则 None）。"""
    actor = latest.current_actor
    assert actor is not None
    latest.completed_actors.append(actor)
    completed = set(latest.completed_actors)
    next_actor = None
    for name in latest.action_order:
        if name not in completed:
            next_actor = name
            break
    latest.current_actor = next_actor
    if next_actor is None:
        latest.is_completed = True
    return next_actor


def simulate_mock_play_cards(card_name: str, targets: List[str]) -> Tuple[bool, str]:
    """开发调试用：模拟出牌（仅追加日志/叙事，不推进 turn）。"""
    ok, err, latest = _mock_validate_turn()
    if not ok:
        return False, err
    assert latest is not None
    actor = latest.current_actor
    assert actor is not None
    target_label = "、".join(targets) if targets else "（自动目标）"
    combat_log = f"{actor} 使用『{card_name}』对 {target_label} 造成伤害。"
    narrative = f"{actor} 打出『{card_name}』，命中目标！"
    latest.cards_log.append(combat_log)
    latest.cards_narrative.append(narrative)
    text = (
        "[bold green]✅ 出牌完成[/]\n"
        "[bold yellow]── 出牌结果 ─────────────────────────────────[/]\n"
        f"  [dim]战斗：[/] {combat_log}\n"
        f"  [dim]叙事：[/] {narrative}"
    )
    return True, text


def simulate_mock_use_consumable(
    item_name: str, targets: List[str]
) -> Tuple[bool, str]:
    """开发调试用：模拟使用消耗品（仅追加日志/叙事，不推进 turn）。"""
    ok, err, latest = _mock_validate_turn()
    if not ok:
        return False, err
    assert latest is not None
    target_label = "、".join(targets) if targets else "（自动目标）"
    combat_log = f"使用『{item_name}』对 {target_label} 生效。"
    narrative = f"一股暖流涌入体内，『{item_name}』的效力发挥了作用。"
    latest.consumable_log.append(combat_log)
    latest.consumable_narrative.append(narrative)
    latest.consumable_use_count += 1
    text = (
        "[bold green]✅ 使用完成[/]\n"
        "[bold yellow]── 使用结果 ─────────────────────────────────[/]\n"
        f"  [dim]战斗：[/] {combat_log}\n"
        f"  [dim]叙事：[/] {narrative}"
    )
    return True, text


def simulate_mock_equip_gear(item_name: str) -> Tuple[bool, str]:
    """开发调试用：模拟使用装备（仅追加日志/叙事，不推进 turn）。"""
    ok, err, latest = _mock_validate_turn()
    if not ok:
        return False, err
    assert latest is not None
    combat_log = f"将『{item_name}』转化为手牌。"
    narrative = f"装备『{item_name}』已就绪。"
    latest.gear_log.append(combat_log)
    latest.gear_narrative.append(narrative)
    latest.gear_equip_count += 1
    text = (
        "[bold green]✅ 使用完成[/]\n"
        "[bold yellow]── 使用结果 ─────────────────────────────────[/]\n"
        f"  [dim]战斗：[/] {combat_log}\n"
        f"  [dim]叙事：[/] {narrative}"
    )
    return True, text


def simulate_mock_pass_turn() -> Tuple[bool, str]:
    """开发调试用：模拟过牌（推进 turn）。"""
    ok, err, latest = _mock_validate_turn()
    if not ok:
        return False, err
    assert latest is not None
    actor = latest.current_actor
    next_actor = _mock_advance_turn(latest)
    lines = [f"[bold green]✅ {actor} 过牌完成[/]"]
    if next_actor is not None:
        lines.append(f"[dim]轮到下一个角色：{next_actor}[/]")
    else:
        lines.append("[dim]所有存活角色均已行动，本回合结束[/]")
    return True, "\n".join(lines)


def simulate_mock_advance_monster_turn() -> Tuple[bool, str]:
    """开发调试用：模拟怪物回合（自动出牌一次 + 推进 turn）。"""
    ok, err, latest = _mock_validate_turn()
    if not ok:
        return False, err
    assert latest is not None
    actor = latest.current_actor
    assert actor is not None
    combat_log = f"{actor} 自动出牌，造成若干伤害。"
    narrative = f"{actor} 发起了攻击！"
    latest.cards_log.append(combat_log)
    latest.cards_narrative.append(narrative)
    next_actor = _mock_advance_turn(latest)
    lines = [
        "[bold green]✅ 怪物回合推进完成[/]",
        "[bold yellow]── 回合结果 ─────────────────────────[/]",
        f"  [dim]战斗：[/] {combat_log}",
        f"  [dim]叙事：[/] {narrative}",
    ]
    if next_actor is not None:
        lines.append(f"[dim]轮到下一个角色：{next_actor}[/]")
    else:
        lines.append("[dim]所有存活角色均已行动，本回合结束[/]")
    return True, "\n".join(lines)


def simulate_mock_collect_loot() -> Tuple[bool, str]:
    """开发调试用：模拟收取战利品（战利品转入背包并清空 CombatLootComponent）。"""
    if not _mock_loot_items:
        return False, "[yellow]（mock）当前没有可收取的战利品。[/]"
    count = len(_mock_loot_items)
    _mock_inventory_items.extend(_mock_loot_items)
    _mock_loot_items.clear()
    return True, f"[bold green]✅ 已收取 {count} 件战利品到背包（mock）[/]"


def simulate_mock_exit_dungeon() -> Tuple[bool, str]:
    """开发调试用：模拟退出副本（无真实会话，仅返回提示）。"""
    return True, "[bold green]✅ 已退出副本（mock）[/]"


def simulate_mock_advance_stage() -> Tuple[bool, str]:
    """开发调试用：模拟进入下一关（current_room_index +1，战斗状态回 INITIALIZATION）。"""
    set_mock_current_room_index(get_mock_current_room_index() + 1)
    set_mock_combat_state(CombatState.INITIALIZATION)
    return True, "[bold green]✅ 已推进到下一关（mock）[/]"


def prepare_mock_post_combat() -> None:
    """开发调试用：预置 POST_COMBAT 结算态（一局已完成回合 + 胜利结果 + 战利品）。"""
    set_mock_combat_state(CombatState.POST_COMBAT)
    set_mock_combat_result(CombatResult.WIN)
    reset_mock_combat_rounds()
    _mock_rounds.append(
        Round(
            completed_actors=[
                MOCK_ACTOR_NAME,
                MOCK_TEAMMATE_NAME,
                MOCK_MONSTER_1_NAME,
                MOCK_MONSTER_2_NAME,
            ],
            action_order=[
                MOCK_ACTOR_NAME,
                MOCK_TEAMMATE_NAME,
                MOCK_MONSTER_1_NAME,
                MOCK_MONSTER_2_NAME,
            ],
            current_actor=None,
            is_completed=True,
            draw_completed=True,
            cards_log=[
                f"{MOCK_ACTOR_NAME} 使用『刺击』对 {MOCK_MONSTER_1_NAME} 造成 5 点伤害。"
            ],
            cards_narrative=[f"{MOCK_ACTOR_NAME} 打出『刺击』，一击命中！"],
        )
    )


###############################################################################################################################################
def _mock_dungeon_actor(
    name: str, actor_type: ActorType, stats: CharacterStats
) -> DungeonActor:
    """构造 CombatRoom.stage.actors 中使用的蓝图 Actor（非 ECS 实时数据）。"""
    return DungeonActor(
        name=name,
        type=actor_type,
        profile=f"{name}（Mock 固定数据，用于本地无服务器调试）",
        base_body="",
        system_message="",
        character_stats=stats,
    )


###############################################################################################################################################
def build_mock_dungeon_room_response() -> DungeonRoomResponse:
    """构造固定的战斗房间响应：2v2（玩家+队友 vs 怪物x2），state=ONGOING。"""
    stage = DungeonStage(
        name=MOCK_STAGE_NAME,
        code_name="mock_dungeon_room",
        type=StageType.DUNGEON,
        profile="模拟副本房间，用于本地无服务器调试。",
        system_message="",
        actors=[
            _mock_dungeon_actor(
                MOCK_ACTOR_NAME,
                ActorType.NPC,
                CharacterStats(hp=18, max_hp=20, attack=6, defense=3),
            ),
            _mock_dungeon_actor(
                MOCK_TEAMMATE_NAME,
                ActorType.NPC,
                CharacterStats(hp=15, max_hp=15, attack=4, defense=4),
            ),
            _mock_dungeon_actor(
                MOCK_MONSTER_1_NAME,
                ActorType.MONSTER,
                CharacterStats(hp=10, max_hp=12, attack=5, defense=2),
            ),
            _mock_dungeon_actor(
                MOCK_MONSTER_2_NAME,
                ActorType.MONSTER,
                CharacterStats(hp=12, max_hp=12, attack=4, defense=2),
            ),
        ],
    )

    combat = Combat(
        name=MOCK_COMBAT_NAME,
        state=_mock_combat_state,
        result=_mock_combat_result,
        retreated=False,
        rounds=list(_mock_rounds),
    )

    room = CombatRoom(stage=stage, combat=combat, image=GeneratedImage())
    return DungeonRoomResponse(room=room)


###############################################################################################################################################
def build_mock_dungeon_state_response() -> DungeonStateResponse:
    """构造固定的副本完整状态响应：固定 2 个房间（当前战斗房间 + 下一关占位房间），
    current_room_index 由 `_mock_current_room_index` 控制（默认 0），用于支持
    「进入下一关（房间）」命令按 `current_room_index` 与 `len(rooms)` 的关系判断
    是否存在下一关。"""
    current_room = build_mock_dungeon_room_response().room

    next_stage = DungeonStage(
        name=MOCK_NEXT_STAGE_NAME,
        code_name="mock_dungeon_next_room",
        type=StageType.DUNGEON,
        profile="模拟副本下一关卡占位数据，用于本地无服务器调试。",
        system_message="",
        actors=[],
    )
    next_room = CombatRoom(
        stage=next_stage,
        combat=Combat(name=f"{MOCK_NEXT_STAGE_NAME}-combat"),
    )

    dungeon = Dungeon(
        name=MOCK_DUNGEON_NAME,
        rooms=[current_room, next_room],
        profile="模拟副本生态描述，用于本地无服务器调试。",
        current_room_index=_mock_current_room_index,
        setup_entities=True,
    )
    return DungeonStateResponse(dungeon=dungeon)


###############################################################################################################################################
def build_mock_stages_state_response() -> StagesStateResponse:
    """构造固定的场景状态映射：单一场景内含玩家、队友与两个怪物。"""
    return StagesStateResponse(
        mapping={
            MOCK_STAGE_NAME: [
                MOCK_ACTOR_NAME,
                MOCK_TEAMMATE_NAME,
                MOCK_MONSTER_1_NAME,
                MOCK_MONSTER_2_NAME,
            ]
        }
    )


###############################################################################################################################################
def _identity_components(name: str, order: int) -> List[ComponentSerialization]:
    return [
        ComponentSerialization(
            name=IdentityComponent.__name__,
            data=IdentityComponent(
                name=name, creation_order=order, entity_id=f"mock-{order}"
            ).model_dump(),
        ),
    ]


###############################################################################################################################################
def _deck_component_serialization(
    name: str, cards: List[Card]
) -> List[ComponentSerialization]:
    """构造 DeckComponent 序列化数据（战斗双方均持有牌库，用于「查阅牌组」命令）。"""
    return [
        ComponentSerialization(
            name=DeckComponent.__name__,
            data=DeckComponent(name=name, cards=cards).model_dump(),
        ),
    ]


###############################################################################################################################################
def _inventory_component_serialization(
    name: str, items: List[AnyItem]
) -> ComponentSerialization:
    """构造 InventoryComponent 序列化数据（仅玩家持有，用于「查阅我方背包」命令）。"""
    return ComponentSerialization(
        name=InventoryComponent.__name__,
        data=InventoryComponent(name=name, items=list(items)).model_dump(),
    )


###############################################################################################################################################
def _combat_loot_component_serialization(
    name: str, items: List[AnyItem]
) -> ComponentSerialization:
    """构造 CombatLootComponent 序列化数据（仅玩家持有，用于「查阅战利品」命令）。"""
    return ComponentSerialization(
        name=CombatLootComponent.__name__,
        data=CombatLootComponent(name=name, items=list(items)).model_dump(),
    )


def _mock_combat_loot_components() -> List[ComponentSerialization]:
    """有战利品时返回 CombatLootComponent 序列化；空则返回空列表（与真实 ECS 一致）。"""
    if not _mock_loot_items:
        return []
    return [_combat_loot_component_serialization(MOCK_ACTOR_NAME, _mock_loot_items)]


###############################################################################################################################################
def _appearance_component_serialization(
    name: str, base_body: str, appearance: str
) -> ComponentSerialization:
    """构造 AppearanceComponent 序列化数据，用于「获取当前外观」命令。"""
    return ComponentSerialization(
        name=AppearanceComponent.__name__,
        data=AppearanceComponent(
            name=name, base_body=base_body, appearance=appearance
        ).model_dump(),
    )


###############################################################################################################################################
def _costume_component_serialization(
    name: str, item: CostumeItem
) -> ComponentSerialization:
    """构造 CostumeComponent 序列化数据（角色已穿戴时装时才存在）。"""
    return ComponentSerialization(
        name=WornCostumeComponent.__name__,
        data=WornCostumeComponent(name=name, item=item).model_dump(),
    )


###############################################################################################################################################
def _appearance_and_costume_components(
    name: str, base_body: str
) -> List[ComponentSerialization]:
    """依据当前 mock 穿戴状态（`_mock_worn_costume_by_actor`）构造 AppearanceComponent，
    若该角色当前已穿戴时装则一并构造 WornCostumeComponent；供「获取当前外观」
    「穿戴/移除时装」等指令联调，appearance 会随 `simulate_mock_wear_costume` 的
    调用结果动态变化（而非固定字面量）。"""
    worn = get_mock_worn_costume(name)
    appearance = (
        base_body if worn is None else f"{base_body}身披{worn.name}，{worn.description}"
    )
    comps = [_appearance_component_serialization(name, base_body, appearance)]
    if worn is not None:
        comps.append(_costume_component_serialization(name, worn))
    return comps


###############################################################################################################################################
def _mock_has_round() -> bool:
    """是否已存在战斗回合（CombatRoundStartSystem 已创建新回合）。"""
    return bool(_mock_rounds)


def _mock_has_drawn() -> bool:
    """本回合是否已抓牌（DrawCardsActionSystem 已填手牌并置 draw_completed）。"""
    return bool(_mock_rounds) and _mock_rounds[-1].draw_completed


def _round_stats_components(name: str) -> List[ComponentSerialization]:
    """有回合时给存活角色挂 RoundStatsComponent（energy=2）。"""
    if not _mock_has_round():
        return []
    return [
        ComponentSerialization(
            name=RoundStatsComponent.__name__,
            data=RoundStatsComponent(name=name, energy=2).model_dump(),
        ),
    ]


###############################################################################################################################################
def _ongoing_battle_pile_components(
    name: str,
    hand_cards: List[Card],
    draw_cards: List[Card],
    exhaust_cards: List[Card],
    discard_cards: List[Card],
) -> List[ComponentSerialization]:
    """构造抓牌后才存在的手牌/抽牌堆/消耗堆/弃牌堆组件。

    未抓牌（尚无回合 / 回合未抽牌）时返回空列表，与真实 ECS 行为一致。"""
    if not _mock_has_drawn():
        return []
    return [
        ComponentSerialization(
            name=HandComponent.__name__,
            data=HandComponent(name=name, cards=hand_cards).model_dump(),
        ),
        ComponentSerialization(
            name=DrawPileComponent.__name__,
            data=DrawPileComponent(name=name, cards=draw_cards).model_dump(),
        ),
        ComponentSerialization(
            name=ExhaustPileComponent.__name__,
            data=ExhaustPileComponent(name=name, cards=exhaust_cards).model_dump(),
        ),
        ComponentSerialization(
            name=DiscardPileComponent.__name__,
            data=DiscardPileComponent(name=name, cards=discard_cards).model_dump(),
        ),
    ]


###############################################################################################################################################
def build_mock_entities_details_response(
    entity_names: List[str],
) -> EntitiesDetailsResponse:
    """构造固定的实体详情响应。忽略入参 entity_names（Mock 模式下恒定返回全量固定实体），
    真实服务端会按 entity_names 过滤，但字段形状完全一致。"""

    stage_serialization = EntitySerialization(
        name=MOCK_STAGE_NAME,
        components=[
            *_identity_components(MOCK_STAGE_NAME, 0),
            ComponentSerialization(
                name=StageComponent.__name__,
                data=StageComponent(
                    name=MOCK_STAGE_NAME, code_name="mock_dungeon_room"
                ).model_dump(),
            ),
            ComponentSerialization(
                name=DungeonComponent.__name__,
                data=DungeonComponent(name=MOCK_STAGE_NAME).model_dump(),
            ),
        ],
    )

    def _actor_serialization(
        name: str,
        order: int,
        stats: CharacterStats,
        role_components: List[ComponentSerialization],
    ) -> EntitySerialization:
        return EntitySerialization(
            name=name,
            components=[
                *_identity_components(name, order),
                ComponentSerialization(
                    name=ActorComponent.__name__,
                    data=ActorComponent(
                        name=name,
                        current_stage=MOCK_STAGE_NAME,
                    ).model_dump(),
                ),
                ComponentSerialization(
                    name=CharacterStatsComponent.__name__,
                    data=CharacterStatsComponent(name=name, stats=stats).model_dump(),
                ),
                *_round_stats_components(name),
                *role_components,
            ],
        )

    player_serialization = _actor_serialization(
        MOCK_ACTOR_NAME,
        1,
        CharacterStats(hp=18, max_hp=20, attack=6, defense=3),
        [
            ComponentSerialization(
                name=PlayerComponent.__name__,
                data=PlayerComponent(player_name=MOCK_USER_NAME).model_dump(),
            ),
            *_appearance_and_costume_components(
                MOCK_ACTOR_NAME,
                base_body="体型精瘦的青年男性，动作敏捷。",
            ),
            *_deck_component_serialization(
                MOCK_ACTOR_NAME,
                [
                    Card(
                        name="斩击",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage=6,
                    ),
                    Card(
                        name="格挡",
                        description="本回合提升自身防御。",
                        cost=1,
                        damage=0,
                    ),
                ],
            ),
            _inventory_component_serialization(MOCK_ACTOR_NAME, _mock_inventory_items),
            *_mock_combat_loot_components(),
            *_ongoing_battle_pile_components(
                MOCK_ACTOR_NAME,
                hand_cards=[
                    Card(
                        name="刺击",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage=5,
                    ),
                ],
                draw_cards=[
                    Card(
                        name="斩击",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage=6,
                    ),
                ],
                exhaust_cards=[],
                discard_cards=[
                    Card(
                        name="格挡",
                        description="本回合提升自身防御。",
                        cost=1,
                        damage=0,
                    ),
                ],
            ),
        ],
    )

    teammate_serialization = _actor_serialization(
        MOCK_TEAMMATE_NAME,
        2,
        CharacterStats(hp=15, max_hp=15, attack=4, defense=4),
        [
            ComponentSerialization(
                name=NPCComponent.__name__,
                data=NPCComponent(name=MOCK_TEAMMATE_NAME).model_dump(),
            ),
            ComponentSerialization(
                name=PartyMemberComponent.__name__,
                data=PartyMemberComponent(name=MOCK_TEAMMATE_NAME).model_dump(),
            ),
            *_appearance_and_costume_components(
                MOCK_TEAMMATE_NAME,
                base_body="身形高挑的女性法师，气质沉静。",
            ),
            *_deck_component_serialization(
                MOCK_TEAMMATE_NAME,
                [
                    Card(
                        name="治疗术",
                        description="为单体友方恢复生命值。",
                        cost=1,
                        damage=0,
                    ),
                    Card(
                        name="重击",
                        description="对单体敌人造成较高物理伤害。",
                        cost=2,
                        damage=9,
                    ),
                ],
            ),
            *_ongoing_battle_pile_components(
                MOCK_TEAMMATE_NAME,
                hand_cards=[
                    Card(
                        name="治疗术",
                        description="为单体友方恢复生命值。",
                        cost=1,
                        damage=0,
                    ),
                ],
                draw_cards=[],
                exhaust_cards=[],
                discard_cards=[],
            ),
        ],
    )

    monster_1_serialization = _actor_serialization(
        MOCK_MONSTER_1_NAME,
        3,
        CharacterStats(hp=10, max_hp=12, attack=5, defense=2),
        [
            ComponentSerialization(
                name=MonsterComponent.__name__,
                data=MonsterComponent(name=MOCK_MONSTER_1_NAME).model_dump(),
            ),
            *_deck_component_serialization(
                MOCK_MONSTER_1_NAME,
                [
                    Card(
                        name="撕咬",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage=5,
                    ),
                ],
            ),
            *_ongoing_battle_pile_components(
                MOCK_MONSTER_1_NAME,
                hand_cards=[
                    Card(
                        name="撕咬",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage=5,
                    ),
                ],
                draw_cards=[],
                exhaust_cards=[],
                discard_cards=[],
            ),
        ],
    )

    monster_2_serialization = _actor_serialization(
        MOCK_MONSTER_2_NAME,
        4,
        CharacterStats(hp=12, max_hp=12, attack=4, defense=2),
        [
            ComponentSerialization(
                name=MonsterComponent.__name__,
                data=MonsterComponent(name=MOCK_MONSTER_2_NAME).model_dump(),
            ),
            *_deck_component_serialization(
                MOCK_MONSTER_2_NAME,
                [
                    Card(
                        name="挥棍",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage=4,
                    ),
                ],
            ),
            *_ongoing_battle_pile_components(
                MOCK_MONSTER_2_NAME,
                hand_cards=[
                    Card(
                        name="挥棍",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage=4,
                    ),
                ],
                draw_cards=[],
                exhaust_cards=[],
                discard_cards=[],
            ),
        ],
    )

    # 全局储物箱：注意与「已穿戴」的时装（如玩家的「旅者披风」）互斥——真实游戏中穿装时
    # 会将时装从 StorageComponent 移出（见 update_appearance_action_system.py），脱下时才归还，
    # 因此这里仅放置当前未被任何角色穿戴的时装，与真实不变式保持一致。
    storage_serialization = EntitySerialization(
        name=MOCK_STORAGE_NAME,
        components=[
            *_identity_components(MOCK_STORAGE_NAME, 5),
            ComponentSerialization(
                name=StorageComponent.__name__,
                data=get_mock_storage_component().model_dump(),
            ),
        ],
    )

    all_entities = [
        stage_serialization,
        player_serialization,
        teammate_serialization,
        monster_1_serialization,
        monster_2_serialization,
        storage_serialization,
    ]

    # 与真实接口行为对齐：仅返回请求中点名的实体（若请求为空则返回全部，便于调试）。
    if not entity_names:
        return EntitiesDetailsResponse(entities=all_entities)

    requested = set(entity_names)
    filtered = [e for e in all_entities if e.name in requested]
    return EntitiesDetailsResponse(entities=filtered)
