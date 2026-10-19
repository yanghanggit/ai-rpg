"""CombatLootSystem 单元测试：掉落推理必须写回怪物记忆（与出牌决策一致）。"""

from typing import List
from unittest.mock import MagicMock, patch

import pytest

from ai_rpg.deepseek import DeepSeekClient
from ai_rpg.entitas import Entity
from ai_rpg.entitas.context import Context
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    AIMessage,
    AppearanceComponent,
    LootComponent,
    MonsterComponent,
    PartyMemberComponent,
)
from ai_rpg.systems.combat_loot_system import CombatLootSystem

_MODULE = "ai_rpg.systems.combat_loot_system"

_LOOT_JSON = """{
  "base_materials": [{"name": "材料.兽骨", "description": "断裂的兽骨。", "count": 2}],
  "part_breaks": [
    {"part_name": "前爪", "broken": true,
     "materials": [{"name": "材料.利爪", "description": "尖锐的爪。", "count": 1}]}
  ]
}"""


def _make_player(context: Context) -> Entity:
    entity = context.create_entity()
    entity._name = "角色.无名"
    entity.add(ActorComponent, entity._name, "stage")
    entity.add(PartyMemberComponent, entity._name)
    entity.add(LootComponent, entity._name, [])
    return entity


def _make_monster(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "stage")
    entity.add(MonsterComponent, name)
    entity.add(AppearanceComponent, name, "体型基础", "一头灰褐色的野狗")
    return entity


@pytest.fixture()
def context() -> Context:
    return Context()


def _make_game(context: Context, monsters: List[Entity], player: Entity) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.current_dungeon_combat_room.combat.is_combat_completed = True
    game.current_dungeon_combat_room.combat.is_won = True
    game.current_dungeon_combat_room.combat.rounds = [MagicMock()]
    game.get_player_entity.return_value = player
    game.get_actors_in_stage.return_value = monsters
    game.get_agent_memory.return_value = MagicMock(messages=[])
    game.resolve_stage_entity.return_value = None
    return game


class TestLootMemory:
    async def test_writes_prompt_and_ai_response_to_monster_memory(
        self, context: Context
    ) -> None:
        """掉落推理必须留痕：human = 请求原文（带 combat_loot 标记），ai = 回包原文。"""
        player = _make_player(context)
        monster = _make_monster(context, "怪物.渡口野狗")
        game = _make_game(context, [monster], player)
        system = CombatLootSystem(game)

        async def fake_batch_chat(clients: List[DeepSeekClient]) -> None:
            for client in clients:
                client._response_ai_message = AIMessage(content=_LOOT_JSON)

        with patch(f"{_MODULE}.batch_chat", side_effect=fake_batch_chat):
            await system.execute()

        # human：请求原文 + 结构化标记
        game.add_human_message.assert_called_once()
        kwargs = game.add_human_message.call_args.kwargs
        assert kwargs["entity"] is monster
        assert kwargs["human_message"].combat_loot == monster.name
        assert "掉落" in kwargs["human_message"].content

        # ai：回包原文
        game.add_ai_message.assert_called_once()
        ai_entity, ai_message = game.add_ai_message.call_args.args
        assert ai_entity is monster
        assert ai_message.content == _LOOT_JSON

        # 掉落照常写入玩家
        assert [item.name for item in player.get(LootComponent).items] == [
            "材料.兽骨",
            "材料.利爪",
        ]

    async def test_records_prompt_only_when_no_response(self, context: Context) -> None:
        """LLM 无回包时只记请求侧，不伪造 AI 回复（add_ai_message 会断言非空）。"""
        player = _make_player(context)
        monster = _make_monster(context, "怪物.渡口野狗")
        game = _make_game(context, [monster], player)
        system = CombatLootSystem(game)

        async def fake_batch_chat(clients: List[DeepSeekClient]) -> None:
            for client in clients:
                client._response_ai_message = None

        with patch(f"{_MODULE}.batch_chat", side_effect=fake_batch_chat):
            await system.execute()

        game.add_human_message.assert_called_once()
        game.add_ai_message.assert_not_called()
        assert player.get(LootComponent).items == []

    async def test_skips_entirely_when_combat_not_won(self, context: Context) -> None:
        """未胜利（或未结束）时不推理、不留痕。"""
        player = _make_player(context)
        monster = _make_monster(context, "怪物.渡口野狗")
        game = _make_game(context, [monster], player)
        game.current_dungeon_combat_room.combat.is_won = False
        system = CombatLootSystem(game)

        await system.execute()

        game.add_human_message.assert_not_called()
        game.add_ai_message.assert_not_called()
