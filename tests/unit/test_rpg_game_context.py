"""
Tests for RPGGame context message management methods:
  - add_human_message
  - add_ai_message
  - filter_messages_by_attributes
  - remove_messages
  - remove_message_range
"""

import pytest
from typing import Any

from src.ai_rpg.models.messages import AIMessage, HumanMessage
from src.ai_rpg.entitas.entity import Entity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def game(sample_game: Any) -> Any:
    """Alias for sample_game — a fully-constructed TCGGame with no blueprint entities."""
    return sample_game


@pytest.fixture
def actor(game: Any) -> Entity:
    """Create a named entity inside the game context."""
    return game._create_entity("TestActor")  # type: ignore[no-any-return]


@pytest.fixture
def second_actor(game: Any) -> Entity:
    """Create a second named entity for multi-entity tests."""
    return game._create_entity("OtherActor")  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# add_human_message
# ---------------------------------------------------------------------------


class TestAddHumanMessage:
    def test_basic(self, game: Any, actor: Entity) -> None:
        """Message is appended; content and type are correct."""
        game.add_human_message(actor, "hello")

        ctx = game.get_agent_context(actor).context
        assert len(ctx) == 1
        msg = ctx[0]
        assert isinstance(msg, HumanMessage)
        assert msg.content == "hello"

    def test_kwargs_stored_as_extra_fields(self, game: Any, actor: Entity) -> None:
        """Extra kwargs are attached to the message via Pydantic extra='allow'."""
        game.add_human_message(
            actor,
            "planning prompt",
            home_actor_planning="TestActor",
            home_actor_full_prompt="full prompt text",
        )

        ctx = game.get_agent_context(actor).context
        msg = ctx[0]
        assert isinstance(msg, HumanMessage)
        assert getattr(msg, "home_actor_planning") == "TestActor"
        assert getattr(msg, "home_actor_full_prompt") == "full prompt text"

    def test_multiple_messages_preserve_order(self, game: Any, actor: Entity) -> None:
        """Multiple adds are appended in insertion order."""
        game.add_human_message(actor, "first")
        game.add_human_message(actor, "second")
        game.add_human_message(actor, "third")

        ctx = game.get_agent_context(actor).context
        assert [m.content for m in ctx] == ["first", "second", "third"]

    def test_different_entities_have_independent_contexts(
        self, game: Any, actor: Entity, second_actor: Entity
    ) -> None:
        """Messages for different entities do not bleed into each other."""
        game.add_human_message(actor, "for actor")
        game.add_human_message(second_actor, "for other")

        assert len(game.get_agent_context(actor).context) == 1
        assert len(game.get_agent_context(second_actor).context) == 1
        assert game.get_agent_context(actor).context[0].content == "for actor"
        assert game.get_agent_context(second_actor).context[0].content == "for other"


# ---------------------------------------------------------------------------
# add_ai_message
# ---------------------------------------------------------------------------


class TestAddAiMessage:
    def test_basic(self, game: Any, actor: Entity) -> None:
        """AIMessage is appended; content and type are correct."""
        ai_msg = AIMessage(content="AI reply")
        game.add_ai_message(actor, ai_msg)

        ctx = game.get_agent_context(actor).context
        assert len(ctx) == 1
        assert isinstance(ctx[0], AIMessage)
        assert ctx[0].content == "AI reply"

    def test_empty_content_raises(self, game: Any, actor: Entity) -> None:
        """Passing an AIMessage with empty content triggers AssertionError."""
        with pytest.raises(AssertionError):
            game.add_ai_message(actor, AIMessage(content=""))

    def test_non_ai_message_raises(self, game: Any, actor: Entity) -> None:
        """Passing a non-AIMessage triggers AssertionError (isinstance guard)."""
        with pytest.raises(AssertionError):
            game.add_ai_message(actor, HumanMessage(content="oops"))

    def test_kwargs_set_as_attributes(self, game: Any, actor: Entity) -> None:
        """kwargs passed to add_ai_message are set as attributes on the message."""
        ai_msg = AIMessage(content="with tag")
        game.add_ai_message(actor, ai_msg, tag="test_tag")

        ctx = game.get_agent_context(actor).context
        assert getattr(ctx[0], "tag") == "test_tag"

    def test_same_message_object_is_stored(self, game: Any, actor: Entity) -> None:
        """The exact message object passed is the one stored (identity check)."""
        ai_msg = AIMessage(content="identity check")
        game.add_ai_message(actor, ai_msg)

        assert game.get_agent_context(actor).context[0] is ai_msg


# ---------------------------------------------------------------------------
# filter_messages_by_attributes
# ---------------------------------------------------------------------------


class TestFilterMessagesByAttributes:
    def test_empty_attributes_returns_empty(self, game: Any, actor: Entity) -> None:
        """Empty attribute dict always returns []."""
        game.add_human_message(actor, "msg", home_actor_planning="TestActor")
        result = game.filter_messages_by_attributes(actor, {})
        assert result == []

    def test_matches_custom_kwarg(self, game: Any, actor: Entity) -> None:
        """Finds a message that has the specified extra field."""
        game.add_human_message(actor, "planning msg", home_actor_planning="TestActor")
        result = game.filter_messages_by_attributes(
            actor, {"home_actor_planning": "TestActor"}
        )
        assert len(result) == 1
        assert result[0].content == "planning msg"

    def test_no_match_returns_empty(self, game: Any, actor: Entity) -> None:
        """Returns [] when no message matches the given attribute value."""
        game.add_human_message(actor, "msg", home_actor_planning="TestActor")
        result = game.filter_messages_by_attributes(
            actor, {"home_actor_planning": "NonExistent"}
        )
        assert result == []

    def test_attribute_not_present_returns_empty(
        self, game: Any, actor: Entity
    ) -> None:
        """Returns [] when no message has the requested attribute at all."""
        game.add_human_message(actor, "plain msg")
        result = game.filter_messages_by_attributes(actor, {"no_such_attr": True})
        assert result == []

    def test_multiple_matches(self, game: Any, actor: Entity) -> None:
        """All matching messages are returned."""
        game.add_human_message(actor, "round 1", home_actor_planning="TestActor")
        game.add_human_message(actor, "round 2", home_actor_planning="TestActor")
        game.add_human_message(actor, "other", home_actor_planning="OtherActor")

        result = game.filter_messages_by_attributes(
            actor, {"home_actor_planning": "TestActor"}
        )
        assert len(result) == 2
        contents = {m.content for m in result}
        assert contents == {"round 1", "round 2"}

    def test_reverse_order_true_returns_newest_first(
        self, game: Any, actor: Entity
    ) -> None:
        """Default reverse_order=True: most-recently-added message is first."""
        game.add_human_message(actor, "older", home_actor_planning="TestActor")
        game.add_human_message(actor, "newer", home_actor_planning="TestActor")

        result = game.filter_messages_by_attributes(
            actor, {"home_actor_planning": "TestActor"}, reverse_order=True
        )
        assert result[0].content == "newer"

    def test_reverse_order_false_returns_oldest_first(
        self, game: Any, actor: Entity
    ) -> None:
        """reverse_order=False: oldest message is first."""
        game.add_human_message(actor, "older", home_actor_planning="TestActor")
        game.add_human_message(actor, "newer", home_actor_planning="TestActor")

        result = game.filter_messages_by_attributes(
            actor, {"home_actor_planning": "TestActor"}, reverse_order=False
        )
        assert result[0].content == "older"

    def test_strict_multi_attribute_match(self, game: Any, actor: Entity) -> None:
        """All specified attributes must match — partial match is not enough."""
        game.add_human_message(
            actor,
            "full match",
            home_actor_planning="TestActor",
            home_actor_full_prompt="prompt",
        )
        game.add_human_message(
            actor,
            "partial only",
            home_actor_planning="TestActor",
        )

        result = game.filter_messages_by_attributes(
            actor,
            {
                "home_actor_planning": "TestActor",
                "home_actor_full_prompt": "prompt",
            },
        )
        assert len(result) == 1
        assert result[0].content == "full match"


# ---------------------------------------------------------------------------
# remove_messages
# ---------------------------------------------------------------------------


class TestRemoveMessages:
    def test_empty_input_returns_zero(self, game: Any, actor: Entity) -> None:
        """Passing an empty list returns 0 and leaves the context unchanged."""
        game.add_human_message(actor, "keep me")
        count = game.remove_messages(actor, [])
        assert count == 0
        assert len(game.get_agent_context(actor).context) == 1

    def test_removes_existing_message(self, game: Any, actor: Entity) -> None:
        """A message that is in the context is removed; return value is 1."""
        game.add_human_message(actor, "to remove")
        msg = game.get_agent_context(actor).context[0]

        count = game.remove_messages(actor, [msg])
        assert count == 1
        assert msg not in game.get_agent_context(actor).context

    def test_removes_multiple_messages(self, game: Any, actor: Entity) -> None:
        """Multiple messages are removed and the correct count is returned."""
        game.add_human_message(actor, "msg1")
        game.add_human_message(actor, "msg2")
        game.add_human_message(actor, "keep")

        ctx = game.get_agent_context(actor).context
        to_remove = [ctx[0], ctx[1]]

        count = game.remove_messages(actor, to_remove)
        assert count == 2
        remaining = game.get_agent_context(actor).context
        assert len(remaining) == 1
        assert remaining[0].content == "keep"

    def test_not_in_context_returns_zero(self, game: Any, actor: Entity) -> None:
        """Passing a message that was never in the context returns 0."""
        game.add_human_message(actor, "keep")
        foreign = HumanMessage(content="not in context")

        count = game.remove_messages(actor, [foreign])
        assert count == 0
        assert len(game.get_agent_context(actor).context) == 1


# ---------------------------------------------------------------------------
# remove_message_range
# ---------------------------------------------------------------------------


class TestRemoveMessageRange:
    def _fill(self, game: Any, actor: Entity, n: int = 5) -> list[Any]:
        """Helper: add n HumanMessages and return all context objects."""
        for i in range(n):
            game.add_human_message(actor, f"msg{i}")
        return list(game.get_agent_context(actor).context)

    def test_same_message_raises(self, game: Any, actor: Entity) -> None:
        """begin == end triggers AssertionError."""
        msgs = self._fill(game, actor, 3)
        with pytest.raises(AssertionError):
            game.remove_message_range(actor, msgs[1], msgs[1])

    def test_basic_range_length(self, game: Any, actor: Entity) -> None:
        """Returned list length equals end_index - begin_index + 1."""
        msgs = self._fill(game, actor, 5)
        deleted = game.remove_message_range(actor, msgs[1], msgs[3])
        assert len(deleted) == 3  # indices 1, 2, 3

    def test_preserves_messages_outside_range(self, game: Any, actor: Entity) -> None:
        """Messages before begin and after end are kept."""
        msgs = self._fill(game, actor, 5)
        game.remove_message_range(actor, msgs[1], msgs[3])

        remaining = game.get_agent_context(actor).context
        assert len(remaining) == 2
        assert remaining[0] is msgs[0]
        assert remaining[1] is msgs[4]

    def test_returns_deleted_message_objects(self, game: Any, actor: Entity) -> None:
        """Return value contains the exact message objects that were deleted."""
        msgs = self._fill(game, actor, 5)
        deleted = game.remove_message_range(actor, msgs[1], msgs[3])

        assert deleted[0] is msgs[1]
        assert deleted[1] is msgs[2]
        assert deleted[2] is msgs[3]

    def test_context_size_after_removal(self, game: Any, actor: Entity) -> None:
        """Context shrinks by exactly the number of deleted messages."""
        msgs = self._fill(game, actor, 5)
        deleted = game.remove_message_range(actor, msgs[0], msgs[2])
        assert len(deleted) == 3
        assert len(game.get_agent_context(actor).context) == 2
