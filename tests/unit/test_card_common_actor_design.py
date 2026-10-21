"""`card_common` 的 actor 上下文入口单测：宿主、上下文口径与「不留痕」。

只测接线与消息形状，会话本身（选型 / 设计）在模块边界被替换：

- system prompt 来自「世界.卡牌设计」实体；
- 目标 actor 的 system prompt 以数据块形式进入任务提示词，而不是整段记忆；
- 角色挂载 `MotifComponent` 时，其 `motif` 作为「## 艺术锚点」数据块注入；未挂则无此块；
- label 为 `世界.卡牌设计|角色.名`；
- `mutate_messages=False`，且 actor 的记忆条数在调用前后不变。
"""

from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock

import pytest

from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import AgentMemory, HumanMessage, SystemMessage
from ai_rpg.systems import card_common
from ai_rpg.systems.card_common import (
    Candidate,
    DesignOutcome,
    SelectionOutcome,
    design_cards_for_actor,
    read_actor_system_prompt,
    resolve_card_design_entity,
    select_prototypes_for_actor,
)

_WORLD_RULES = "你是这个世界的卡牌设计者……"
_ACTOR_PROMPT = (
    "# 角色.无名\n\n你扮演角色: 角色.无名\n\n## 角色设定\n\n沉默，观察多于开口。"
)


def _entity(name: str) -> MagicMock:
    """构造带 `.name` 的实体替身（`MagicMock(name=...)` 只改 repr，不改属性）。"""
    entity = MagicMock()
    entity.name = name
    return entity


def _make_game() -> Tuple[MagicMock, MagicMock, MagicMock]:
    """构造最小 game：一个卡牌设计世界实体 + 一个 actor 的持久记忆。"""
    world_entity = _entity("世界.卡牌设计")
    actor_entity = _entity("角色.无名")

    memories: Dict[str, AgentMemory] = {
        "世界.卡牌设计": AgentMemory(
            name="世界.卡牌设计", messages=[SystemMessage(content=_WORLD_RULES)]
        ),
        "角色.无名": AgentMemory(
            name="角色.无名",
            messages=[
                SystemMessage(content=_ACTOR_PROMPT),
                HumanMessage(content="（此前的对话）"),
            ],
        ),
    }

    game = MagicMock(spec=DBGGame)
    game.get_group.return_value.entities = {world_entity}
    game.get_agent_memory.side_effect = lambda entity: memories[entity.name]
    return game, world_entity, actor_entity


def _make_candidate(name: str) -> Candidate:
    from ai_rpg.models import Card

    return Candidate(
        card=Card(name=name, description="", source="角色.无名"),
        archetype="",
        archetype_subtype="",
        summary="",
        design="",
    )


#######################################################################################################################################
def test_resolve_card_design_entity_requires_single_host() -> None:
    """蓝图缺少卡牌设计实体时直接失败（指向刷新命令）。"""
    game = MagicMock(spec=DBGGame)
    game.get_group.return_value.entities = set()

    with pytest.raises(AssertionError, match="setup_demo"):
        resolve_card_design_entity(game)


#######################################################################################################################################
def test_read_actor_system_prompt_reads_first_message() -> None:
    """actor 的设定取 `messages[0]`，不是整段记忆。"""
    game, _, actor_entity = _make_game()

    assert read_actor_system_prompt(game, actor_entity) == _ACTOR_PROMPT


#######################################################################################################################################
async def test_selection_uses_world_system_and_actor_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """选型：system = 世界契约，actor 设定进任务提示词，会话不落 actor 记忆。"""
    game, _, actor_entity = _make_game()
    memory_before = len(game.get_agent_memory(actor_entity).messages)
    captured: Dict[str, Any] = {}

    async def _fake_selection(
        name: str, index: List[Any], messages: List[Any], **kwargs: Any
    ) -> SelectionOutcome:
        captured.update(name=name, messages=messages, **kwargs)
        return SelectionOutcome(ok=True, selected=["p1", "p2"], total=2)

    monkeypatch.setattr(card_common, "run_card_selection_session", _fake_selection)

    outcome = await select_prototypes_for_actor(
        game,
        actor_name="角色.无名",
        actor_system_prompt=_ACTOR_PROMPT,
        index=[],
        size=2,
        prompt="# 任务：挑选原型",
    )

    assert bool(outcome)
    assert captured["name"] == "世界.卡牌设计|角色.无名"
    assert [m.content for m in captured["messages"]] == [_WORLD_RULES]
    assert captured["prompt"].startswith("## 你要为之设计的角色")
    assert _ACTOR_PROMPT.strip() in captured["prompt"]
    assert captured["mutate_messages"] is False
    assert len(game.get_agent_memory(actor_entity).messages) == memory_before


#######################################################################################################################################
async def test_design_uses_world_system_and_leaves_no_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """设计：上下文口径同选型；会话不写入 actor 记忆。"""
    game, _, actor_entity = _make_game()
    captured: Dict[str, Any] = {}

    async def _fake_design(
        name: str, candidates: List[Any], messages: List[Any], **kwargs: Any
    ) -> DesignOutcome:
        captured.update(name=name, messages=messages, **kwargs)
        return DesignOutcome(
            ok=True, designed=len(candidates), total=len(candidates), affixes=0
        )

    monkeypatch.setattr(card_common, "run_card_design_session", _fake_design)

    actor_memory_before = len(game.get_agent_memory(actor_entity).messages)
    candidates = [_make_candidate("余刃")]

    outcome = await design_cards_for_actor(
        game,
        actor_name="角色.无名",
        actor_system_prompt=_ACTOR_PROMPT,
        candidates=candidates,
        context="## 投入材料\n\n- 材料.铁锭",
    )

    assert outcome.ok
    assert captured["name"] == "世界.卡牌设计|角色.无名"
    assert [m.content for m in captured["messages"]] == [_WORLD_RULES]
    # 任务提示词里同时有 actor 设定与调用方上下文
    assert _ACTOR_PROMPT.strip() in captured["context"]
    assert "材料.铁锭" in captured["context"]
    # 未传 actor_motif：不注入艺术锚点块，口径与旧版本一致
    assert "## 艺术锚点" not in captured["context"]
    assert captured["mutate_messages"] is False
    assert len(game.get_agent_memory(actor_entity).messages) == actor_memory_before


#######################################################################################################################################
async def test_design_injects_actor_motif_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`actor_motif` 非空时，作为「## 艺术锚点」块跟在角色设定之后。"""
    game, _, _ = _make_game()
    captured: Dict[str, Any] = {}

    async def _fake_design(
        name: str, candidates: List[Any], messages: List[Any], **kwargs: Any
    ) -> DesignOutcome:
        captured.update(name=name, messages=messages, **kwargs)
        return DesignOutcome(
            ok=True, designed=len(candidates), total=len(candidates), affixes=0
        )

    monkeypatch.setattr(card_common, "run_card_design_session", _fake_design)

    await design_cards_for_actor(
        game,
        actor_name="角色.无名",
        actor_system_prompt=_ACTOR_PROMPT,
        candidates=[_make_candidate("余刃")],
        actor_motif="**母题**: 不属于此地的旧斗篷",
    )

    context = captured["context"]
    assert "## 艺术锚点" in context
    assert "**母题**: 不属于此地的旧斗篷" in context
    # 角色设定在前，艺术锚点在后
    assert context.index("## 你要为之设计的角色") < context.index("## 艺术锚点")
