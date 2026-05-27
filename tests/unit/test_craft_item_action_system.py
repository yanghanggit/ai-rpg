"""CraftItemActionSystem 单元测试。

覆盖范围：
  _build_craft_prompt
    - 材料名称、数量、描述出现在输出中
    - TargetType 枚举值（非硬编码字符串）出现在规则说明与 JSON 示例中

  _build_craft_result_message
    - 材料摘要格式正确（顿号拼接）
    - 物品名称与描述出现在输出中
    - 有效果时以 "  - " 前缀列出
    - 无效果时显示占位文字

  CraftItemActionSystem.filter
    - 同时拥有 CraftItemAction + InventoryComponent 时通过
    - 缺少 CraftItemAction 时拒绝
    - 缺少 InventoryComponent 时拒绝

  CraftItemActionSystem._craft_item（通过 react 驱动）
    - 无 WorkshopComponent 实体时提前退出，背包不变
    - LLM 返回空字符串时不修改背包
    - JSON 解析失败时不修改背包
    - 解析到的 name 为空时不修改背包
    - 未知 target_type 降级为 SELF_ONLY，制造仍然成功
    - 制造成功：背包新增 ConsumableItem，效果/target_type 与 LLM 返回一致
    - 制造成功：材料 count > 1 时递减
    - 制造成功：材料 count = 1 时从背包移除
    - 制造成功：多种材料各自扣除 1 个
    - 制造成功：调用 add_human_message 注入 context
"""

import json
from typing import List
from unittest.mock import AsyncMock, patch

import pytest

from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.player_session import PlayerSession
from src.ai_rpg.game.tcg_game import TCGGame
from src.ai_rpg.models import (
    ActorComponent,
    InventoryComponent,
    WorldComponent,
    WorkshopComponent,
)
from src.ai_rpg.models.actions import CraftItemAction
from src.ai_rpg.models.entities import Actor, CharacterSheet
from src.ai_rpg.models.items import ConsumableItem, MaterialItem
from src.ai_rpg.models.stats import CharacterStats
from src.ai_rpg.models.target_type import TargetType
from src.ai_rpg.models.world import Blueprint, World
from src.ai_rpg.models.dungeon import Dungeon
from src.ai_rpg.systems.craft_item_action_system import (
    CraftItemActionSystem,
    _build_craft_prompt,
    _build_craft_result_message,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_material(name: str = "草叶", count: int = 2) -> MaterialItem:
    return MaterialItem(name=name, description=f"{name} 的描述", count=count)


def _make_consumable(
    name: str = "治愈药水",
    effects: List[str] | None = None,
    target_type: TargetType = TargetType.SELF_ONLY,
) -> ConsumableItem:
    return ConsumableItem(
        name=name,
        description=f"{name} 的描述",
        count=1,
        target_type=target_type,
        affixes=effects or [],
    )


def _make_game() -> TCGGame:
    actor = Actor(
        name="角色.旅行者.无名氏",
        character_sheet=CharacterSheet(
            name="sheet", type="hero", profile="", base_body=""
        ),
        system_message="",
        character_stats=CharacterStats(hp=20, max_hp=20),
    )
    blueprint = Blueprint(
        name="test",
        player_actor=actor.name,
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
        dungeon=Dungeon(name="", rooms=[], ecology=""),
        blueprint=blueprint,
    )
    session = PlayerSession(name="p1", actor=actor.name, game="test")
    return TCGGame(name="test", player_session=session, world=world)


def _make_actor_entity(
    game: TCGGame,
    name: str = "角色.旅行者.无名氏",
    materials: List[MaterialItem] | None = None,
) -> Entity:
    entity = game._create_entity(name)
    entity.add(ActorComponent, name, "sheet", "场景.石台广场")
    entity.add(InventoryComponent, name, list(materials or []))
    return entity


def _make_workshop_entity(game: TCGGame) -> Entity:
    ws = game._create_entity("世界系统.制造工坊")
    ws.add(WorldComponent, "世界系统.制造工坊")
    ws.add(WorkshopComponent, "世界系统.制造工坊")
    return ws


def _llm_response(
    name: str = "合成物",
    description: str = "描述",
    target_type: str = TargetType.SELF_ONLY,
    effects: List[str] | None = None,
) -> str:
    return json.dumps(
        {
            "name": name,
            "description": description,
            "target_type": target_type,
            "effects": effects or [],
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# _build_craft_prompt
# ---------------------------------------------------------------------------


class TestBuildCraftPrompt:
    def test_contains_material_name(self) -> None:
        mat = _make_material("沙漠草叶", count=3)
        prompt = _build_craft_prompt([mat])
        assert "沙漠草叶" in prompt

    def test_contains_material_count(self) -> None:
        mat = _make_material("沙漠草叶", count=3)
        prompt = _build_craft_prompt([mat])
        assert "3" in prompt

    def test_contains_material_description(self) -> None:
        mat = _make_material("毒蝶触须", count=1)
        prompt = _build_craft_prompt([mat])
        assert mat.description in prompt

    def test_contains_target_type_enum_values(self) -> None:
        """prompt 中的 target_type 规则必须使用枚举值（小写），而非硬编码大写字符串。"""
        prompt = _build_craft_prompt([_make_material()])
        assert str(TargetType.SELF_ONLY) in prompt
        assert str(TargetType.ENEMY_SINGLE) in prompt
        assert str(TargetType.ENEMY_ALL) in prompt

    def test_multiple_materials_all_present(self) -> None:
        mats = [_make_material("草叶"), _make_material("触须")]
        prompt = _build_craft_prompt(mats)
        assert "草叶" in prompt
        assert "触须" in prompt


# ---------------------------------------------------------------------------
# _build_craft_result_message
# ---------------------------------------------------------------------------


class TestBuildCraftResultMessage:
    def test_material_summary_uses_chinese_comma(self) -> None:
        mats = [_make_material("草叶"), _make_material("触须")]
        item = _make_consumable("合成物")
        msg = _build_craft_result_message(mats, item)
        assert "草叶、触须" in msg

    def test_contains_item_name(self) -> None:
        mats = [_make_material()]
        item = _make_consumable("涩毒粉")
        msg = _build_craft_result_message(mats, item)
        assert "涩毒粉" in msg

    def test_contains_item_description(self) -> None:
        mats = [_make_material()]
        item = _make_consumable("涩毒粉")
        msg = _build_craft_result_message(mats, item)
        assert item.description in msg

    def test_effects_listed_with_prefix(self) -> None:
        mats = [_make_material()]
        item = _make_consumable(effects=["中毒:持续掉血", "减速:行动迟缓"])
        msg = _build_craft_result_message(mats, item)
        assert "  - 中毒:持续掉血" in msg
        assert "  - 减速:行动迟缓" in msg

    def test_no_effects_shows_placeholder(self) -> None:
        mats = [_make_material()]
        item = _make_consumable(effects=[])
        msg = _build_craft_result_message(mats, item)
        assert "无特殊效果" in msg


# ---------------------------------------------------------------------------
# CraftItemActionSystem.filter
# ---------------------------------------------------------------------------


class TestCraftItemActionSystemFilter:
    def _system(self, game: TCGGame) -> CraftItemActionSystem:
        return CraftItemActionSystem(game)

    def test_passes_entity_with_all_required_components(self) -> None:
        game = _make_game()
        mat = _make_material()
        entity = _make_actor_entity(game, materials=[mat])
        entity.add(CraftItemAction, entity.name, [mat])
        assert self._system(game).filter(entity) is True

    def test_excludes_entity_without_craft_action(self) -> None:
        game = _make_game()
        entity = _make_actor_entity(game)
        assert self._system(game).filter(entity) is False

    def test_excludes_entity_without_inventory(self) -> None:
        game = _make_game()
        mat = _make_material()
        entity = game._create_entity("actor")
        entity.add(ActorComponent, "actor", "sheet", "stage")
        entity.add(CraftItemAction, "actor", [mat])
        assert self._system(game).filter(entity) is False


# ---------------------------------------------------------------------------
# CraftItemActionSystem._craft_item（通过 react 驱动）
# ---------------------------------------------------------------------------


class TestCraftItemActionSystemReact:
    """所有 LLM 调用均通过 patch 替换，避免网络请求。"""

    @pytest.mark.asyncio
    async def test_no_workshop_entity_exits_early(self) -> None:
        """缺少 WorkshopComponent 实体时，背包内容不变。"""
        game = _make_game()
        mat = _make_material(count=2)
        entity = _make_actor_entity(game, materials=[mat])
        entity.add(CraftItemAction, entity.name, [mat])
        # 不创建 workshop 实体
        await CraftItemActionSystem(game).react([entity])
        assert len(entity.get(InventoryComponent).items) == 1  # 原材料未变

    @pytest.mark.asyncio
    async def test_empty_llm_response_skips_craft(self) -> None:
        game = _make_game()
        mat = _make_material(count=2)
        entity = _make_actor_entity(game, materials=[mat])
        entity.add(CraftItemAction, entity.name, [mat])
        _make_workshop_entity(game)

        with patch(
            "src.ai_rpg.systems.craft_item_action_system.DeepSeekClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.response_content = ""
            MockClient.return_value = instance

            await CraftItemActionSystem(game).react([entity])

        assert len(entity.get(InventoryComponent).items) == 1  # 材料未被消耗

    @pytest.mark.asyncio
    async def test_invalid_json_skips_craft(self) -> None:
        game = _make_game()
        mat = _make_material(count=2)
        entity = _make_actor_entity(game, materials=[mat])
        entity.add(CraftItemAction, entity.name, [mat])
        _make_workshop_entity(game)

        with patch(
            "src.ai_rpg.systems.craft_item_action_system.DeepSeekClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.response_content = "这不是 JSON"
            MockClient.return_value = instance

            await CraftItemActionSystem(game).react([entity])

        assert len(entity.get(InventoryComponent).items) == 1

    @pytest.mark.asyncio
    async def test_empty_name_skips_craft(self) -> None:
        game = _make_game()
        mat = _make_material(count=2)
        entity = _make_actor_entity(game, materials=[mat])
        entity.add(CraftItemAction, entity.name, [mat])
        _make_workshop_entity(game)

        with patch(
            "src.ai_rpg.systems.craft_item_action_system.DeepSeekClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.response_content = _llm_response(name="")
            MockClient.return_value = instance

            await CraftItemActionSystem(game).react([entity])

        assert len(entity.get(InventoryComponent).items) == 1

    @pytest.mark.asyncio
    async def test_unknown_target_type_falls_back_to_self_only(self) -> None:
        game = _make_game()
        mat = _make_material(count=2)
        entity = _make_actor_entity(game, materials=[mat])
        entity.add(CraftItemAction, entity.name, [mat])
        _make_workshop_entity(game)

        with patch(
            "src.ai_rpg.systems.craft_item_action_system.DeepSeekClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.response_content = _llm_response(
                name="神秘药剂", target_type="UNKNOWN_VALUE"
            )
            MockClient.return_value = instance

            await CraftItemActionSystem(game).react([entity])

        items = entity.get(InventoryComponent).items
        consumables = [i for i in items if isinstance(i, ConsumableItem)]
        assert len(consumables) == 1
        assert consumables[0].target_type == TargetType.SELF_ONLY

    @pytest.mark.asyncio
    async def test_successful_craft_adds_consumable_to_inventory(self) -> None:
        game = _make_game()
        mat = _make_material(count=2)
        entity = _make_actor_entity(game, materials=[mat])
        entity.add(CraftItemAction, entity.name, [mat])
        _make_workshop_entity(game)

        with patch(
            "src.ai_rpg.systems.craft_item_action_system.DeepSeekClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.response_content = _llm_response(
                name="涩毒粉",
                target_type=str(TargetType.ENEMY_SINGLE),
                effects=["涩毒:持续掉血"],
            )
            MockClient.return_value = instance

            await CraftItemActionSystem(game).react([entity])

        items = entity.get(InventoryComponent).items
        consumables = [i for i in items if isinstance(i, ConsumableItem)]
        assert len(consumables) == 1
        assert consumables[0].name == "涩毒粉"
        assert consumables[0].target_type == TargetType.ENEMY_SINGLE
        assert consumables[0].affixes == ["涩毒:持续掉血"]

    @pytest.mark.asyncio
    async def test_successful_craft_decrements_material_count(self) -> None:
        game = _make_game()
        mat = _make_material("草叶", count=3)
        entity = _make_actor_entity(game, materials=[mat])
        entity.add(CraftItemAction, entity.name, [mat])
        _make_workshop_entity(game)

        with patch(
            "src.ai_rpg.systems.craft_item_action_system.DeepSeekClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.response_content = _llm_response(name="药剂")
            MockClient.return_value = instance

            await CraftItemActionSystem(game).react([entity])

        items = entity.get(InventoryComponent).items
        materials = [i for i in items if isinstance(i, MaterialItem)]
        assert len(materials) == 1
        assert materials[0].count == 2

    @pytest.mark.asyncio
    async def test_successful_craft_removes_material_when_count_is_one(self) -> None:
        game = _make_game()
        mat = _make_material("草叶", count=1)
        entity = _make_actor_entity(game, materials=[mat])
        entity.add(CraftItemAction, entity.name, [mat])
        _make_workshop_entity(game)

        with patch(
            "src.ai_rpg.systems.craft_item_action_system.DeepSeekClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.response_content = _llm_response(name="药剂")
            MockClient.return_value = instance

            await CraftItemActionSystem(game).react([entity])

        items = entity.get(InventoryComponent).items
        materials = [i for i in items if isinstance(i, MaterialItem)]
        assert len(materials) == 0

    @pytest.mark.asyncio
    async def test_successful_craft_deducts_multiple_materials(self) -> None:
        game = _make_game()
        mat1 = _make_material("草叶", count=2)
        mat2 = _make_material("触须", count=1)
        entity = _make_actor_entity(game, materials=[mat1, mat2])
        entity.add(CraftItemAction, entity.name, [mat1, mat2])
        _make_workshop_entity(game)

        with patch(
            "src.ai_rpg.systems.craft_item_action_system.DeepSeekClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.response_content = _llm_response(name="混合药剂")
            MockClient.return_value = instance

            await CraftItemActionSystem(game).react([entity])

        items = entity.get(InventoryComponent).items
        materials = {i.name: i.count for i in items if isinstance(i, MaterialItem)}
        assert materials.get("草叶") == 1  # count 3→2... wait, was 2→1
        assert "触须" not in materials  # count 1→0，已移除

    @pytest.mark.asyncio
    async def test_successful_craft_calls_add_human_message(self) -> None:
        game = _make_game()
        mat = _make_material("草叶", count=1)
        entity = _make_actor_entity(game, materials=[mat])
        entity.add(CraftItemAction, entity.name, [mat])
        _make_workshop_entity(game)

        with patch(
            "src.ai_rpg.systems.craft_item_action_system.DeepSeekClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.response_content = _llm_response(name="涩毒粉")
            MockClient.return_value = instance

            with patch.object(game, "add_human_message") as mock_add:
                await CraftItemActionSystem(game).react([entity])

        mock_add.assert_called_once()
        call_args = mock_add.call_args
        assert call_args[0][0] is entity
        message: str = call_args[0][1]
        assert "草叶" in message
        assert "涩毒粉" in message
