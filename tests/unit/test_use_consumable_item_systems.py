"""使用消耗品系统单元测试。

覆盖范围：
  UseConsumableItemActionSystem
    - filter：组件过滤逻辑
    - react：跳过（非 ongoing）、消耗 energy、递减/移除背包物品、
             记录 completed_actors、调用 advance_turn、注入对话消息、广播预告

  UseConsumableItemArbitrationSystem
    - filter：组件过滤逻辑
    - react：跳过（非 ongoing）
    - _apply_item_arbitration_result：HP 更新、格挡更新、状态效果描述补丁、
                                       追加 combat_log/narrative、触发 AddStatusEffectsAction
    - _process_zero_health_entities：添加 DeathComponent
    - _trigger_add_status_effects：空 effects 跳过、为每个受影响实体添加动作
"""

from typing import Any, List, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.ai_rpg.models.messages import AIMessage

from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.player_session import PlayerSession
from src.ai_rpg.game.tcg_game import TCGGame
from src.ai_rpg.models import (
    ActorComponent,
    CharacterStatsComponent,
    DungeonComponent,
    InventoryComponent,
    RoundStatsComponent,
    StageComponent,
    StatusEffectsComponent,
)
from src.ai_rpg.models.actions import AddStatusEffectsAction, UseConsumableItemAction
from src.ai_rpg.models.cards import StatusEffect, EffectPhase
from src.ai_rpg.models.combat import CombatState, Round
from src.ai_rpg.models.dungeon import CombatRoom, Dungeon
from src.ai_rpg.models.entities import (
    Actor,
    CharacterSheet,
    Stage,
    StageProfile,
    StageType,
)
from src.ai_rpg.models.stats import CharacterStats
from src.ai_rpg.models.items import ConsumableItem
from src.ai_rpg.models.target_type import TargetType
from src.ai_rpg.models.world import Blueprint, World
from src.ai_rpg.systems.use_consumable_item_action_system import (
    UseConsumableItemActionSystem,
)
from src.ai_rpg.systems.use_consumable_item_arbitration_system import (
    UseConsumableItemArbitrationSystem,
)
from src.ai_rpg.models.components import DeathComponent


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_consumable_item(
    name: str = "治愈药水",
    count: int = 1,
    effects: List[str] | None = None,
    target_type: TargetType = TargetType.SELF_ONLY,
) -> ConsumableItem:
    return ConsumableItem(
        name=name,
        description=f"{name} 描述",
        count=count,
        target_type=target_type,
        effects=effects or [],
    )


def _make_stage_entity(game: Any, stage_name: str, is_dungeon: bool = True) -> Entity:
    entity = cast(Entity, game._create_entity(stage_name))
    entity.add(StageComponent, stage_name, "")
    if is_dungeon:
        entity.add(DungeonComponent, stage_name)
    return entity


def _make_actor_entity(
    game: Any,
    actor_name: str,
    stage_name: str,
    hp: int = 20,
    energy: int = 3,
    items: List[Any] | None = None,
) -> Entity:
    entity = cast(Entity, game._create_entity(actor_name))
    entity.add(ActorComponent, actor_name, "sheet", stage_name)
    entity.add(CharacterStatsComponent, actor_name, CharacterStats(hp=hp, max_hp=hp))
    entity.add(RoundStatsComponent, actor_name, energy)
    entity.add(InventoryComponent, actor_name, items or [])
    return entity


def _make_game(actor_name: str = "hero", stage_name: str = "cave") -> TCGGame:
    actor = Actor(
        name=actor_name,
        character_sheet=CharacterSheet(
            name=f"{actor_name}_sheet",
            type="hero",
            profile="",
            base_body="human body",
        ),
        system_message="",
        character_stats=CharacterStats(hp=20, max_hp=20),
    )
    stage = Stage(
        name=stage_name,
        stage_profile=StageProfile(
            name=f"{stage_name}_profile", type=StageType.DUNGEON, profile=""
        ),
        system_message="",
        actors=[actor],
    )
    combat_room = CombatRoom(stage=stage)
    dungeon = Dungeon(
        name="test_dungeon",
        rooms=[combat_room],
        ecology="",
        current_room_index=0,
    )
    blueprint = Blueprint(
        name="test",
        player_actor=actor_name,
        player_only_stage="home",
        campaign_setting="",
        stages=[],
        world_systems=[],
    )
    world = World(
        entity_counter=0,
        home_planning_turn_index=0,
        entities_serialization=[],
        agents_context={},
        dungeon=dungeon,
        blueprint=blueprint,
    )
    session = PlayerSession(name="p1", actor=actor_name, game="test")
    return TCGGame(name="test", player_session=session, world=world)


def _set_ongoing(game: TCGGame, actor_names: List[str]) -> Round:
    """将地下城设为 ONGOING 并创建含有 actor_order_snapshots 的首个回合。"""
    dungeon = game.current_dungeon
    assert dungeon.current_combat_room is not None
    round_ = Round(actor_order_snapshots=[list(actor_names)])
    dungeon.current_combat_room.combat.state = CombatState.ONGOING
    dungeon.current_combat_room.combat.rounds.append(round_)
    return round_


# ---------------------------------------------------------------------------
# UseConsumableItemActionSystem — filter
# ---------------------------------------------------------------------------


class TestUseConsumableItemActionSystemFilter:
    def _system(self) -> UseConsumableItemActionSystem:
        return UseConsumableItemActionSystem(_make_game())

    def _entity_with_all_components(
        self, game: TCGGame, item: ConsumableItem
    ) -> Entity:
        entity = _make_actor_entity(game, "hero", "cave", items=[item])
        entity.add(UseConsumableItemAction, "hero", item, [])
        return entity

    def test_passes_entity_with_all_required_components(self) -> None:
        game = _make_game()
        item = _make_consumable_item()
        entity = self._entity_with_all_components(game, item)
        system = UseConsumableItemActionSystem(game)
        assert system.filter(entity) is True

    def test_excludes_entity_without_action_component(self) -> None:
        game = _make_game()
        entity = _make_actor_entity(game, "hero", "cave")
        system = UseConsumableItemActionSystem(game)
        assert system.filter(entity) is False

    def test_excludes_entity_without_actor_component(self) -> None:
        game = _make_game()
        item = _make_consumable_item()
        entity = game._create_entity("hero")
        entity.add(UseConsumableItemAction, "hero", item, [])
        entity.add(RoundStatsComponent, "hero", 3)
        entity.add(InventoryComponent, "hero", [item])
        # ActorComponent missing — filter should reject
        assert UseConsumableItemActionSystem(game).filter(entity) is False

    def test_excludes_entity_without_round_stats(self) -> None:
        game = _make_game()
        item = _make_consumable_item()
        entity = game._create_entity("hero")
        entity.add(ActorComponent, "hero", "sheet", "cave")
        entity.add(UseConsumableItemAction, "hero", item, [])
        entity.add(InventoryComponent, "hero", [item])
        assert UseConsumableItemActionSystem(game).filter(entity) is False

    def test_excludes_entity_without_inventory(self) -> None:
        game = _make_game()
        item = _make_consumable_item()
        entity = game._create_entity("hero")
        entity.add(ActorComponent, "hero", "sheet", "cave")
        entity.add(UseConsumableItemAction, "hero", item, [])
        entity.add(RoundStatsComponent, "hero", 3)
        assert UseConsumableItemActionSystem(game).filter(entity) is False


# ---------------------------------------------------------------------------
# UseConsumableItemActionSystem — react
# ---------------------------------------------------------------------------


class TestUseConsumableItemActionSystemReact:
    @pytest.mark.asyncio
    async def test_skips_when_dungeon_not_ongoing(self) -> None:
        """战斗未进行中时 react 不做任何修改。"""
        game = _make_game()
        # 不调用 _set_ongoing，state 默认为 NONE
        item = _make_consumable_item(count=1)
        entity = _make_actor_entity(game, "hero", "cave", energy=3, items=[item])
        entity.add(UseConsumableItemAction, "hero", item, [])
        system = UseConsumableItemActionSystem(game)
        await system.react([entity])
        # energy 不变
        assert entity.get(RoundStatsComponent).energy == 3

    @pytest.mark.asyncio
    async def test_decrements_energy_by_one(self) -> None:
        game = _make_game()
        item = _make_consumable_item(count=1)
        entity = _make_actor_entity(game, "hero", "cave", energy=3, items=[item])
        entity.add(UseConsumableItemAction, "hero", item, [])
        _make_stage_entity(game, "cave")
        round_ = _set_ongoing(game, ["hero"])
        round_.current_turn_actor_name = "hero"

        system = UseConsumableItemActionSystem(game)
        await system.react([entity])

        assert entity.get(RoundStatsComponent).energy == 2

    @pytest.mark.asyncio
    async def test_removes_item_from_inventory_when_count_is_one(self) -> None:
        game = _make_game()
        item = _make_consumable_item(count=1)
        entity = _make_actor_entity(game, "hero", "cave", energy=3, items=[item])
        entity.add(UseConsumableItemAction, "hero", item, [])
        _make_stage_entity(game, "cave")
        round_ = _set_ongoing(game, ["hero"])
        round_.current_turn_actor_name = "hero"

        await UseConsumableItemActionSystem(game).react([entity])

        assert len(entity.get(InventoryComponent).items) == 0

    @pytest.mark.asyncio
    async def test_decrements_item_count_when_count_gt_one(self) -> None:
        game = _make_game()
        item = _make_consumable_item(count=3)
        entity = _make_actor_entity(game, "hero", "cave", energy=3, items=[item])
        entity.add(UseConsumableItemAction, "hero", item, [])
        _make_stage_entity(game, "cave")
        round_ = _set_ongoing(game, ["hero"])
        round_.current_turn_actor_name = "hero"

        await UseConsumableItemActionSystem(game).react([entity])

        remaining = entity.get(InventoryComponent).items
        assert len(remaining) == 1
        assert remaining[0].count == 2

    @pytest.mark.asyncio
    async def test_appends_actor_to_completed_actors(self) -> None:
        game = _make_game()
        item = _make_consumable_item(count=1)
        entity = _make_actor_entity(game, "hero", "cave", energy=3, items=[item])
        entity.add(UseConsumableItemAction, "hero", item, [])
        _make_stage_entity(game, "cave")
        round_ = _set_ongoing(game, ["hero"])
        round_.current_turn_actor_name = "hero"

        await UseConsumableItemActionSystem(game).react([entity])

        assert "hero" in round_.completed_actors

    @pytest.mark.asyncio
    async def test_injects_human_message_for_actor(self) -> None:
        """react 应调用 add_human_message 为使用者注入使用上下文。"""
        game = _make_game()
        item = _make_consumable_item(count=1)
        entity = _make_actor_entity(game, "hero", "cave", energy=3, items=[item])
        entity.add(UseConsumableItemAction, "hero", item, [])
        _make_stage_entity(game, "cave")
        round_ = _set_ongoing(game, ["hero"])
        round_.current_turn_actor_name = "hero"

        with patch.object(
            game, "add_human_message", wraps=game.add_human_message
        ) as spy:
            await UseConsumableItemActionSystem(game).react([entity])

        # 至少有一次调用是针对 actor entity 的
        actor_calls = [
            call
            for call in spy.call_args_list
            if call.kwargs.get("entity") is entity
            or (call.args and call.args[0] is entity)
        ]
        assert len(actor_calls) >= 1

    @pytest.mark.asyncio
    async def test_broadcasts_item_notice_to_stage(self) -> None:
        """react 应调用 broadcast_to_stage 广播使用预告。"""
        game = _make_game()
        item = _make_consumable_item(count=1)
        entity = _make_actor_entity(game, "hero", "cave", energy=3, items=[item])
        entity.add(UseConsumableItemAction, "hero", item, [])
        _make_stage_entity(game, "cave")
        round_ = _set_ongoing(game, ["hero"])
        round_.current_turn_actor_name = "hero"

        with patch.object(
            game, "broadcast_to_stage", wraps=game.broadcast_to_stage
        ) as spy:
            await UseConsumableItemActionSystem(game).react([entity])

        assert spy.call_count >= 1


# ---------------------------------------------------------------------------
# UseConsumableItemArbitrationSystem — filter
# ---------------------------------------------------------------------------


class TestUseConsumableItemArbitrationSystemFilter:
    def test_passes_entity_with_action_and_round_stats(self) -> None:
        game = _make_game()
        item = _make_consumable_item()
        entity = _make_actor_entity(game, "hero", "cave")
        entity.add(UseConsumableItemAction, "hero", item, [])
        assert UseConsumableItemArbitrationSystem(game).filter(entity) is True

    def test_excludes_entity_without_action(self) -> None:
        game = _make_game()
        entity = _make_actor_entity(game, "hero", "cave")
        assert UseConsumableItemArbitrationSystem(game).filter(entity) is False

    def test_excludes_entity_without_round_stats(self) -> None:
        game = _make_game()
        item = _make_consumable_item()
        entity = game._create_entity("hero")
        entity.add(UseConsumableItemAction, "hero", item, [])
        # RoundStatsComponent missing
        assert UseConsumableItemArbitrationSystem(game).filter(entity) is False


# ---------------------------------------------------------------------------
# UseConsumableItemArbitrationSystem — react (skip when not ongoing)
# ---------------------------------------------------------------------------


class TestUseConsumableItemArbitrationSystemReact:
    @pytest.mark.asyncio
    async def test_skips_when_dungeon_not_ongoing(self) -> None:
        """战斗未进行中时 react 不触发仲裁（不调用 LLM）。"""
        game = _make_game()
        item = _make_consumable_item()
        entity = _make_actor_entity(game, "hero", "cave")
        entity.add(UseConsumableItemAction, "hero", item, [])
        system = UseConsumableItemArbitrationSystem(game)

        with patch.object(
            system, "_request_consumable_arbitration", new_callable=AsyncMock
        ) as mock_arb:
            await system.react([entity])

        mock_arb.assert_not_called()


# ---------------------------------------------------------------------------
# UseConsumableItemArbitrationSystem — _apply_item_arbitration_result
# ---------------------------------------------------------------------------


def _make_mock_chat_client(response_json: str) -> MagicMock:
    """创建模拟 DeepSeekClient，返回指定的 JSON 响应。"""
    client = MagicMock()
    client.response_content = f"```json\n{response_json}\n```"
    client.compressed_prompt = "compressed prompt"
    client.prompt = "full prompt"
    client.response_ai_message = AIMessage(content="ai response")
    return client


class TestApplyItemArbitrationResult:
    def _setup(
        self,
        actor_hp: int = 10,
        actor_energy: int = 2,
        item_effects: List[str] | None = None,
    ) -> tuple[
        TCGGame,
        UseConsumableItemArbitrationSystem,
        Entity,
        Entity,
        UseConsumableItemAction,
    ]:
        """返回 (game, system, stage_entity, actor_entity, action)。"""
        game = _make_game()
        stage_entity = _make_stage_entity(game, "cave")
        _set_ongoing(game, ["hero"])
        actor_entity = _make_actor_entity(
            game, "hero", "cave", hp=actor_hp, energy=actor_energy
        )
        item = _make_consumable_item(effects=item_effects or [])
        actor_entity.add(UseConsumableItemAction, "hero", item, [])
        action = actor_entity.get(UseConsumableItemAction)
        system = UseConsumableItemArbitrationSystem(game)
        return game, system, stage_entity, actor_entity, action

    def test_updates_hp_from_final_stats(self) -> None:
        # actor starts at 10 HP with max 20; healing to 15 should be accepted
        game = _make_game()
        stage_entity = _make_stage_entity(game, "cave")
        _set_ongoing(game, ["hero"])
        actor_entity = _make_actor_entity(game, "hero", "cave", hp=10)
        # Raise max_hp so the healed value (15) isn't capped
        cs = actor_entity.get(CharacterStatsComponent)
        actor_entity.replace(
            CharacterStatsComponent, "hero", CharacterStats(hp=10, max_hp=20)
        )
        item = _make_consumable_item(effects=[])
        actor_entity.add(UseConsumableItemAction, "hero", item, [])
        action = actor_entity.get(UseConsumableItemAction)
        system = UseConsumableItemArbitrationSystem(game)
        response_json = '{"combat_log":"log","narrative":"narr","final_stats":{"hero":{"hp":15,"block":0,"status_effect_patches":[]}}}'
        chat_client = _make_mock_chat_client(response_json)

        system._apply_item_arbitration_result(
            stage_entity, chat_client, actor_entity, action
        )

        assert game.compute_character_stats(actor_entity).hp == 15

    def test_patches_status_effect_description(self) -> None:
        game, system, stage, actor, action = self._setup()
        # 先给 actor 添加一个状态效果
        effect = StatusEffect(
            name="中毒",
            description="每回合损失 2 HP（剩余 3 次）",
            phase=EffectPhase.ARBITRATION,
            duration=3,
        )
        actor.add(StatusEffectsComponent, "hero", [effect])

        response_json = (
            '{"combat_log":"log","narrative":"narr","final_stats":{"hero":{'
            '"hp":20,"block":0,"status_effect_patches":[{"name":"中毒","description":"每回合损失 2 HP（剩余 2 次）"}]'
            "}}}"
        )
        chat_client = _make_mock_chat_client(response_json)
        system._apply_item_arbitration_result(stage, chat_client, actor, action)

        updated = actor.get(StatusEffectsComponent).status_effects[0]
        assert updated.description == "每回合损失 2 HP（剩余 2 次）"

    def test_skips_unknown_status_effect_patch(self) -> None:
        """status_effect_patches 中不存在的 name 应被跳过，不抛异常。"""
        game, system, stage, actor, action = self._setup()
        actor.add(StatusEffectsComponent, "hero", [])

        response_json = (
            '{"combat_log":"log","narrative":"narr","final_stats":{"hero":{'
            '"hp":20,"block":0,"status_effect_patches":[{"name":"不存在效果","description":"x"}]'
            "}}}"
        )
        chat_client = _make_mock_chat_client(response_json)
        # 不应抛出异常
        system._apply_item_arbitration_result(stage, chat_client, actor, action)

    def test_appends_combat_log_and_narrative_to_latest_round(self) -> None:
        game, system, stage, actor, action = self._setup()
        response_json = '{"combat_log":"战斗日志","narrative":"演出描述","final_stats":{"hero":{"hp":20,"block":0,"status_effect_patches":[]}}}'
        chat_client = _make_mock_chat_client(response_json)

        system._apply_item_arbitration_result(stage, chat_client, actor, action)

        latest = game.current_dungeon.latest_round
        assert latest is not None
        assert "战斗日志" in latest.combat_log
        assert "演出描述" in latest.narrative

    def test_triggers_add_status_effects_when_item_has_effects(self) -> None:
        game, system, stage, actor, action = self._setup(
            item_effects=["[眩晕]:眩晕目标"]
        )
        response_json = '{"combat_log":"log","narrative":"narr","final_stats":{"hero":{"hp":20,"block":0,"status_effect_patches":[]}}}'
        chat_client = _make_mock_chat_client(response_json)

        with patch.object(
            system,
            "_trigger_add_status_effects",
            wraps=system._trigger_add_status_effects,
        ) as spy:
            system._apply_item_arbitration_result(stage, chat_client, actor, action)

        spy.assert_called_once()
        assert actor.has(AddStatusEffectsAction)

    def test_does_not_trigger_add_status_effects_when_effects_empty(self) -> None:
        game, system, stage, actor, action = self._setup(item_effects=[])
        response_json = '{"combat_log":"log","narrative":"narr","final_stats":{"hero":{"hp":20,"block":0,"status_effect_patches":[]}}}'
        chat_client = _make_mock_chat_client(response_json)

        system._apply_item_arbitration_result(stage, chat_client, actor, action)

        assert not actor.has(AddStatusEffectsAction)


# ---------------------------------------------------------------------------
# UseConsumableItemArbitrationSystem — _process_zero_health_entities
# ---------------------------------------------------------------------------


class TestProcessZeroHealthEntities:
    def test_adds_death_component_to_entity_with_zero_hp(self) -> None:
        game = _make_game()
        entity = _make_actor_entity(game, "hero", "cave", hp=0)

        game.process_zero_health_entities()

        assert entity.has(DeathComponent)

    def test_does_not_add_death_component_to_entity_with_positive_hp(self) -> None:
        game = _make_game()
        entity = _make_actor_entity(game, "hero", "cave", hp=10)

        game.process_zero_health_entities()

        assert not entity.has(DeathComponent)

    def test_skips_entity_already_dead(self) -> None:
        """已有 DeathComponent 的实体不应再次处理。"""
        game = _make_game()
        entity = _make_actor_entity(game, "hero", "cave", hp=0)
        entity.add(DeathComponent, "hero")

        # 调用两次也不应抛异常（replace 语义下幂等）
        game.process_zero_health_entities()
        assert entity.has(DeathComponent)


# ---------------------------------------------------------------------------
# UseConsumableItemArbitrationSystem — _trigger_add_status_effects
# ---------------------------------------------------------------------------


class TestTriggerAddStatusEffects:
    def _make_action(self, effects: List[str]) -> UseConsumableItemAction:
        item = _make_consumable_item(effects=effects)
        return UseConsumableItemAction(name="hero", item=item, targets=[])

    def test_skips_when_item_effects_empty(self) -> None:
        game = _make_game()
        actor = _make_actor_entity(game, "hero", "cave")
        action = self._make_action(effects=[])
        system = UseConsumableItemArbitrationSystem(game)

        system._trigger_add_status_effects(actor, action, ["hero"])

        assert not actor.has(AddStatusEffectsAction)

    def test_adds_action_for_each_affected_entity(self) -> None:
        game = _make_game()
        actor = _make_actor_entity(game, "hero", "cave")
        enemy = _make_actor_entity(game, "slime", "cave")
        action = self._make_action(effects=["[减速]:移动力减半"])
        system = UseConsumableItemArbitrationSystem(game)

        system._trigger_add_status_effects(actor, action, ["hero", "slime"])

        assert actor.has(AddStatusEffectsAction)
        assert enemy.has(AddStatusEffectsAction)
