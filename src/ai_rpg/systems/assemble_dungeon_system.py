"""副本组装系统：把生成阶段的中间产物落成副本、房间与场景实体，产物写入磁盘。"""

from typing import Dict, Final, List, Set, final, override

from loguru import logger

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorType,
    AnyDungeonRoom,
    CharacterStats,
    CombatRoom,
    Dungeon,
    DungeonActorDraft,
    DungeonDraft,
    GenerateDungeonAction,
    OpeningRoom,
    StageType,
    create_actor,
    create_stage,
)
from ..paths import DUNGEONS_DIR, DUNGEONS_DRAFTS_DIR


####################################################################################################################################
@final
class AssembleDungeonSystem(ReactiveProcessor):
    """副本组装系统"""

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
        draft = self._game._dungeon_draft
        if draft is None:
            logger.error("[AssembleDungeonSystem] 中间过程数据缺失，跳过")
            return

        if not draft.rooms:
            logger.error("[AssembleDungeonSystem] rooms 为空，无法构建 Dungeon")
            return

        logger.info(f"[AssembleDungeonSystem] 开始: dungeon={draft.dungeon_name}")

        # 组装 Dungeon 实体树，并把最终产物写入 DUNGEONS_DIR
        dungeon = self._build_dungeon(draft)
        dungeon_path = DUNGEONS_DIR / f"{dungeon.name}.json"
        dungeon_path.write_text(dungeon.model_dump_json(indent=4), encoding="utf-8")

        # 落一份中间过程数据（草稿）到 DUNGEONS_DRAFTS_DIR，便于回溯
        draft_path = DUNGEONS_DRAFTS_DIR / f"{draft.dungeon_name}.json"
        draft_path.write_text(draft.model_dump_json(indent=4), encoding="utf-8")

        logger.info(
            f"[AssembleDungeonSystem] 完成并保存: {dungeon_path} ({len(dungeon.rooms)} rooms)，草稿: {draft_path}"
        )

    ####################################################################################################################################
    @staticmethod
    def _deduplicate_name(seen: Set[str], name: str) -> str:
        """若 name 已在 seen 中，追加 _2/_3/... 直到唯一；否则直接返回原名。"""
        if name not in seen:
            seen.add(name)
            return name
        counter = 2
        while f"{name}_{counter}" in seen:
            counter += 1
        unique = f"{name}_{counter}"
        seen.add(unique)
        logger.warning(
            f"[AssembleDungeonSystem] 名称重复，已重命名: '{name}' → '{unique}'"
        )
        return unique

    ####################################################################################################################################
    def _build_dungeon(self, draft: DungeonDraft) -> Dungeon:
        """将中间过程数据组装为完整 Dungeon 实体树（纯数据，无 LLM 调用）。"""
        actors_by_room: Dict[str, List[DungeonActorDraft]] = {}
        for actor_draft in draft.actors:
            actors_by_room.setdefault(actor_draft.room_name, []).append(actor_draft)

        seen_room_names: set[str] = set()
        seen_actor_names: set[str] = set()
        rooms: List[AnyDungeonRoom] = []

        # 组装每个 room 对应的房间
        for i, room_draft in enumerate(draft.rooms, start=1):

            # 处理 room_name 重复问题
            room_name = self._deduplicate_name(seen_room_names, room_draft.room_name)

            # 创建 Stage 实体
            stage = create_stage(
                name=room_name,
                stage_type=StageType.DUNGEON,
                profile=room_draft.profile,
                campaign_setting=self._game._world.blueprint.campaign_setting,
                system_rules=self._game._world.blueprint.system_rules,
            )

            # 根据 room_type 创建对应的房间类型
            if room_draft.room_type == "opening":
                stage.actors = []
                rooms.append(OpeningRoom(stage=stage))
                logger.info(
                    f"[AssembleDungeonSystem] Room {i}/{len(draft.rooms)} 构建完成:\n  type:   opening\n  stage:  {stage.name}"
                )
            elif room_draft.room_type == "combat":
                actors = []
                for actor_draft in actors_by_room.get(room_draft.room_name, []):
                    actor = create_actor(
                        name=self._deduplicate_name(
                            seen_actor_names, actor_draft.actor_name
                        ),
                        actor_type=ActorType.MONSTER,
                        profile=actor_draft.profile,
                        base_body=actor_draft.base_body,
                        character_stats=CharacterStats(),
                        campaign_setting=self._game._world.blueprint.campaign_setting,
                        system_rules=self._game._world.blueprint.system_rules,
                    )
                    # 牌库由 AssembleDungeonDeckSystem 后续从卡牌原型库组建并润色
                    actors.append(actor)

                # 将 actors 分配给 stage，并创建 CombatRoom 实体
                stage.actors = actors
                rooms.append(CombatRoom(stage=stage))
                logger.info(
                    f"[AssembleDungeonSystem] Room {i}/{len(draft.rooms)} 构建完成:\n  type:   combat\n  stage:  {stage.name}\n  actors ({len(actors)}): "
                    + ", ".join(a.name for a in actors)
                )

        # 组装 Dungeon 实体
        dungeon = Dungeon(
            name=draft.dungeon_name,
            profile=draft.profile,
            rooms=rooms,
        )
        logger.info(
            f"[AssembleDungeonSystem] Dungeon 组装完成: {dungeon.name} ({len(dungeon.rooms)} rooms)"
        )
        return dungeon
