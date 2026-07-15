"""战斗房间本地调试用固定 Mock 数据。

服务器尚未启动时（`--dev-screen combat-room` 跳过登录，`session is None`），
`CombatRoomScreen` 使用本模块构造的固定 2v2（玩家+队友 vs 怪物x2）数据，
数据形状与真实服务端响应（DungeonRoomResponse / StagesStateResponse /
EntitiesDetailsResponse）严格一致，均通过真实 Pydantic 模型构造而非裸 dict，
保证 schema 变化时能第一时间在此处报错。
"""

from typing import Final, List
from ..models import (
    ActorComponent,
    AnyItem,
    Card,
    Combat,
    CombatLootComponent,
    CombatResult,
    CombatRoom,
    CombatState,
    CharacterSheet,
    CharacterStats,
    CharacterStatsComponent,
    ComponentSerialization,
    ConsumableItem,
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
    Stage as DungeonStage,
    StageComponent,
    StageProfile,
    StagesStateResponse,
    Actor as DungeonActor,
)

# ── 固定身份信息（session is None 时使用，替代真实登录会话）──
MOCK_USER_NAME: Final[str] = "mock_user"
MOCK_GAME_NAME: Final[str] = "mock_game"
MOCK_ACTOR_NAME: Final[str] = "艾伦"

MOCK_STAGE_NAME: Final[str] = "回廊-地下城"
MOCK_TEAMMATE_NAME: Final[str] = "赛琳"
MOCK_MONSTER_1_NAME: Final[str] = "哥布林-甲"
MOCK_MONSTER_2_NAME: Final[str] = "哥布林-乙"

MOCK_COMBAT_NAME: Final[str] = f"{MOCK_STAGE_NAME}-combat"

MOCK_DUNGEON_NAME: Final[str] = "回廊地下城"
MOCK_NEXT_STAGE_NAME: Final[str] = "回廊-地下城-次关"

# ── 可变 mock 战斗状态（仅开发调试用：模拟服务端状态推进，例如确认开始战斗后置为 ONGOING）──
_mock_combat_state: CombatState = CombatState.INITIALIZATION

# ── 可变 mock 地下城房间索引（仅开发调试用：模拟"进入下一关"后 current_room_index 前进）──
_mock_current_room_index: int = 0


def set_mock_combat_state(state: CombatState) -> None:
    """开发调试用：切换 mock 战斗状态（如确认开始战斗后置为 ONGOING）。"""
    global _mock_combat_state
    _mock_combat_state = state


def get_mock_combat_state() -> CombatState:
    return _mock_combat_state


def set_mock_current_room_index(index: int) -> None:
    """开发调试用：切换 mock 地下城当前房间索引（如"进入下一关"成功后前进）。"""
    global _mock_current_room_index
    _mock_current_room_index = index


def get_mock_current_room_index() -> int:
    return _mock_current_room_index


###############################################################################################################################################
def _mock_dungeon_actor(
    name: str, actor_type: str, stats: CharacterStats
) -> DungeonActor:
    """构造 CombatRoom.stage.actors 中使用的蓝图 Actor（非 ECS 实时数据）。"""
    return DungeonActor(
        name=name,
        character_sheet=CharacterSheet(
            name=name,
            type=actor_type,
            profile=f"{name}（Mock 固定数据，用于本地无服务器调试）",
            base_body="",
        ),
        system_message="",
        character_stats=stats,
        custom_item=None,
        keywords=[],
    )


###############################################################################################################################################
def build_mock_dungeon_room_response() -> DungeonRoomResponse:
    """构造固定的战斗房间响应：2v2（玩家+队友 vs 怪物x2），state=ONGOING。"""
    stage = DungeonStage(
        name=MOCK_STAGE_NAME,
        stage_profile=StageProfile(
            name=MOCK_STAGE_NAME,
            type="Dungeon",
            profile="模拟地下城房间，用于本地无服务器调试。",
        ),
        system_message="",
        actors=[
            _mock_dungeon_actor(
                MOCK_ACTOR_NAME,
                "NPC",
                CharacterStats(
                    hp=18, max_hp=20, attack=6, defense=3, energy=2, speed=5
                ),
            ),
            _mock_dungeon_actor(
                MOCK_TEAMMATE_NAME,
                "NPC",
                CharacterStats(
                    hp=15, max_hp=15, attack=4, defense=4, energy=2, speed=4
                ),
            ),
            _mock_dungeon_actor(
                MOCK_MONSTER_1_NAME,
                "Monster",
                CharacterStats(
                    hp=10, max_hp=12, attack=5, defense=2, energy=1, speed=3
                ),
            ),
            _mock_dungeon_actor(
                MOCK_MONSTER_2_NAME,
                "Monster",
                CharacterStats(
                    hp=12, max_hp=12, attack=4, defense=2, energy=1, speed=2
                ),
            ),
        ],
    )

    combat = Combat(
        name=MOCK_COMBAT_NAME,
        state=_mock_combat_state,
        result=CombatResult.NONE,
        retreated=False,
        rounds=[
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
        ],
    )

    room = CombatRoom(stage=stage, combat=combat, image=GeneratedImage())
    return DungeonRoomResponse(room=room)


###############################################################################################################################################
def build_mock_dungeon_state_response() -> DungeonStateResponse:
    """构造固定的地下城完整状态响应：固定 2 个房间（当前战斗房间 + 下一关占位房间），
    current_room_index 由 `_mock_current_room_index` 控制（默认 0），用于支持
    「进入下一关（房间）」命令按 `current_room_index` 与 `len(rooms)` 的关系判断
    是否存在下一关。"""
    current_room = build_mock_dungeon_room_response().room

    next_stage = DungeonStage(
        name=MOCK_NEXT_STAGE_NAME,
        stage_profile=StageProfile(
            name=MOCK_NEXT_STAGE_NAME,
            type="Dungeon",
            profile="模拟地下城下一关卡占位数据，用于本地无服务器调试。",
        ),
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
        ecology="模拟地下城生态描述，用于本地无服务器调试。",
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
    name: str, cards: List[Card], keywords: List[str]
) -> ComponentSerialization:
    """构造 DeckComponent 序列化数据（战斗双方均持有牌库，用于「查阅牌组」命令）。"""
    return ComponentSerialization(
        name=DeckComponent.__name__,
        data=DeckComponent(name=name, cards=cards, keywords=keywords).model_dump(),
    )


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


###############################################################################################################################################
def _ongoing_battle_pile_components(
    name: str,
    hand_cards: List[Card],
    draw_cards: List[Card],
    exhaust_cards: List[Card],
    discard_cards: List[Card],
) -> List[ComponentSerialization]:
    """构造 ONGOING 阶段才存在的手牌/抽牌堆/消耗堆/弃牌堆组件。

    INITIALIZATION 阶段返回空列表，与真实 ECS 行为一致（这些子堆仅在
    CombatRoundInitSystem/DeckGenerationSystem 等战斗内系统运行后才会创建）。"""
    if _mock_combat_state != CombatState.ONGOING:
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
                    name=MOCK_STAGE_NAME, character_sheet_name=MOCK_STAGE_NAME
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
                        character_sheet_name=name,
                        current_stage=MOCK_STAGE_NAME,
                    ).model_dump(),
                ),
                ComponentSerialization(
                    name=CharacterStatsComponent.__name__,
                    data=CharacterStatsComponent(name=name, stats=stats).model_dump(),
                ),
                *role_components,
            ],
        )

    player_serialization = _actor_serialization(
        MOCK_ACTOR_NAME,
        1,
        CharacterStats(hp=18, max_hp=20, attack=6, defense=3, energy=2, speed=5),
        [
            ComponentSerialization(
                name=PlayerComponent.__name__,
                data=PlayerComponent(player_name=MOCK_USER_NAME).model_dump(),
            ),
            _deck_component_serialization(
                MOCK_ACTOR_NAME,
                [
                    Card(
                        name="斩击",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage_dealt=6,
                    ),
                    Card(
                        name="格挡",
                        description="本回合提升自身防御。",
                        cost=1,
                        damage_dealt=0,
                    ),
                ],
                keywords=["剑术", "稳健"],
            ),
            _inventory_component_serialization(
                MOCK_ACTOR_NAME,
                [
                    ConsumableItem(name="治疗药水", description="恢复少量生命值。"),
                    ConsumableItem(name="力量药剂", description="短暂提升攻击力。"),
                    GearItem(
                        name="淬炼长剑",
                        description="一把普通但锐利的长剑，适合新手冒险者。",
                        stat_bonuses=CharacterStats(
                            hp=0, max_hp=0, attack=2, defense=0, energy=0, speed=1
                        ),
                    ),
                ],
            ),
            _combat_loot_component_serialization(
                MOCK_ACTOR_NAME,
                [
                    MaterialItem(
                        name="哥布林牙", description="哥布林掉落的牙齿，可用于合成。"
                    ),
                    MaterialItem(
                        name="哥布林皮", description="哥布林掉落的皮革，可用于合成。"
                    ),
                ],
            ),
            *_ongoing_battle_pile_components(
                MOCK_ACTOR_NAME,
                hand_cards=[
                    Card(
                        name="刺击",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage_dealt=5,
                    ),
                ],
                draw_cards=[
                    Card(
                        name="斩击",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage_dealt=6,
                    ),
                ],
                exhaust_cards=[],
                discard_cards=[
                    Card(
                        name="格挡",
                        description="本回合提升自身防御。",
                        cost=1,
                        damage_dealt=0,
                    ),
                ],
            ),
        ],
    )

    teammate_serialization = _actor_serialization(
        MOCK_TEAMMATE_NAME,
        2,
        CharacterStats(hp=15, max_hp=15, attack=4, defense=4, energy=2, speed=4),
        [
            ComponentSerialization(
                name=NPCComponent.__name__,
                data=NPCComponent(name=MOCK_TEAMMATE_NAME).model_dump(),
            ),
            ComponentSerialization(
                name=PartyMemberComponent.__name__,
                data=PartyMemberComponent(name=MOCK_TEAMMATE_NAME).model_dump(),
            ),
            _deck_component_serialization(
                MOCK_TEAMMATE_NAME,
                [
                    Card(
                        name="治疗术",
                        description="为单体友方恢复生命值。",
                        cost=1,
                        damage_dealt=0,
                    ),
                    Card(
                        name="重击",
                        description="对单体敌人造成较高物理伤害。",
                        cost=2,
                        damage_dealt=9,
                    ),
                ],
                keywords=["辅助", "法术"],
            ),
            *_ongoing_battle_pile_components(
                MOCK_TEAMMATE_NAME,
                hand_cards=[
                    Card(
                        name="治疗术",
                        description="为单体友方恢复生命值。",
                        cost=1,
                        damage_dealt=0,
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
        CharacterStats(hp=10, max_hp=12, attack=5, defense=2, energy=1, speed=3),
        [
            ComponentSerialization(
                name=MonsterComponent.__name__,
                data=MonsterComponent(name=MOCK_MONSTER_1_NAME).model_dump(),
            ),
            _deck_component_serialization(
                MOCK_MONSTER_1_NAME,
                [
                    Card(
                        name="撕咬",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage_dealt=5,
                    ),
                ],
                keywords=["野蛮"],
            ),
            *_ongoing_battle_pile_components(
                MOCK_MONSTER_1_NAME,
                hand_cards=[
                    Card(
                        name="撕咬",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage_dealt=5,
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
        CharacterStats(hp=12, max_hp=12, attack=4, defense=2, energy=1, speed=2),
        [
            ComponentSerialization(
                name=MonsterComponent.__name__,
                data=MonsterComponent(name=MOCK_MONSTER_2_NAME).model_dump(),
            ),
            _deck_component_serialization(
                MOCK_MONSTER_2_NAME,
                [
                    Card(
                        name="挥棍",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage_dealt=4,
                    ),
                ],
                keywords=["野蛮"],
            ),
            *_ongoing_battle_pile_components(
                MOCK_MONSTER_2_NAME,
                hand_cards=[
                    Card(
                        name="挥棍",
                        description="对单体敌人造成物理伤害。",
                        cost=1,
                        damage_dealt=4,
                    ),
                ],
                draw_cards=[],
                exhaust_cards=[],
                discard_cards=[],
            ),
        ],
    )

    all_entities = [
        stage_serialization,
        player_serialization,
        teammate_serialization,
        monster_1_serialization,
        monster_2_serialization,
    ]

    # 与真实接口行为对齐：仅返回请求中点名的实体（若请求为空则返回全部，便于调试）。
    if not entity_names:
        return EntitiesDetailsResponse(entities_serialization=all_entities)

    requested = set(entity_names)
    filtered = [e for e in all_entities if e.name in requested]
    return EntitiesDetailsResponse(entities_serialization=filtered)
