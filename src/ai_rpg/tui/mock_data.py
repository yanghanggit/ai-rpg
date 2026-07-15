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
    Card,
    Combat,
    CombatResult,
    CombatRoom,
    CombatState,
    CharacterSheet,
    CharacterStats,
    CharacterStatsComponent,
    ComponentSerialization,
    ConsumableItem,
    DeckComponent,
    DungeonComponent,
    DungeonRoomResponse,
    EntitiesDetailsResponse,
    EntitySerialization,
    GeneratedImage,
    IdentityComponent,
    InventoryComponent,
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
        state=CombatState.INITIALIZATION,
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
    name: str, items: List[ConsumableItem]
) -> ComponentSerialization:
    """构造 InventoryComponent 序列化数据（仅玩家持有，用于「查阅我方背包」命令）。"""
    return ComponentSerialization(
        name=InventoryComponent.__name__,
        data=InventoryComponent(name=name, items=list(items)).model_dump(),
    )


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
