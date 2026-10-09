"""
Tests for the Matcher class in the entitas framework.
"""

import pytest

from ai_rpg.entitas import Context, Entity, Matcher
from ecs_testing import Health, Name, Position, Velocity


def _make_entity() -> Entity:
    return Context().create_entity()


class TestMatcherConstruction:
    def test_positional_args_become_all_of(self) -> None:
        matcher = Matcher(Position, Velocity)
        assert matcher.all_of == (Position, Velocity)
        assert matcher.any_of is None
        assert matcher.none_of is None

    def test_keyword_conditions(self) -> None:
        matcher = Matcher(
            all_of=(Position,),
            any_of=(Velocity, Health),
            none_of=(Name,),
        )
        assert matcher.all_of == (Position,)
        assert matcher.any_of == (Velocity, Health)
        assert matcher.none_of == (Name,)

    def test_list_and_single_type_are_normalized(self) -> None:
        assert Matcher(all_of=[Position, Velocity]).all_of == (Position, Velocity)
        assert Matcher(all_of=Position).all_of == (Position,)

    def test_invalid_specification_raises(self) -> None:
        with pytest.raises(TypeError):
            Matcher(all_of=123)  # type: ignore[arg-type]


class TestMatcherMatching:
    def test_all_of(self) -> None:
        entity = _make_entity()
        entity.add(Position, 1, 2)

        assert Matcher(Position).matches(entity)
        assert not Matcher(Position, Velocity).matches(entity)

        entity.add(Velocity, 3, 4)
        assert Matcher(Position, Velocity).matches(entity)

    def test_any_of(self) -> None:
        entity = _make_entity()
        entity.add(Position, 1, 2)

        assert Matcher(any_of=(Position, Velocity)).matches(entity)
        assert Matcher(any_of=(Velocity, Health)).matches(entity) is False

    def test_none_of(self) -> None:
        entity = _make_entity()
        entity.add(Position, 1, 2)

        assert Matcher(none_of=(Velocity,)).matches(entity)
        assert not Matcher(none_of=(Position,)).matches(entity)

    def test_combined_conditions(self) -> None:
        entity = _make_entity()
        entity.add(Position, 1, 2)
        entity.add(Velocity, 3, 4)

        assert Matcher(Position, any_of=(Velocity, Health), none_of=(Name,)).matches(
            entity
        )
        assert not Matcher(Position, any_of=(Health,), none_of=(Name,)).matches(entity)


class TestMatcherIdentity:
    def test_equality(self) -> None:
        assert Matcher(Position) == Matcher(Position)
        assert Matcher(Position) != Matcher(Velocity)
        assert Matcher(Position, any_of=(Velocity,)) == Matcher(
            Position, any_of=(Velocity,)
        )

    def test_hashable_and_usable_as_dict_key(self) -> None:
        table = {Matcher(Position): "position"}
        assert table[Matcher(Position)] == "position"

    def test_repr_contains_component_names(self) -> None:
        text = repr(Matcher(Position, none_of=(Velocity,)))
        assert "Position" in text
        assert "Velocity" in text
