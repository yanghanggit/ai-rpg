"""Name-keyed dump / load for the core of a :class:`Context`.

The representation is intentionally minimal: it captures only what is needed to
rebuild a context's core (its entities and their components). Every other member
of ``Context`` / ``Entity`` is runtime state derived at load time (component
pools, slot handles, groups, event wiring, name indexes), so it is never stored.

The output is a plain nested mapping keyed by entity name, which keeps it
JSON-friendly, readable and diffable::

    {
        "hero": {
            "IdentityComponent": {"name": "hero", "creation_order": 1, ...},
            "Position": {"x": 1.0, "y": 2.0},
        },
    }

Component type names are resolved back to classes through an injected
:data:`ComponentResolver`, so this module stays free of any component registry
(``entitas`` must not depend on the game layer).
"""

from typing import Any, Callable, Dict, Iterable, Optional, Type

from .components import Component
from .context import Context
from .entity import Entity

#: A single component's data: field name -> value.
ComponentData = Dict[str, Any]

#: One entity's components: component type name -> component data.
EntityData = Dict[str, ComponentData]

#: A context core: entity name -> entity data.
ContextData = Dict[str, EntityData]

#: Resolves a component type name plus its data back to a component class.
ComponentResolver = Callable[[str, ComponentData], Type[Component]]

#: Predicate deciding whether a component type should be dumped.
ComponentFilter = Callable[[Type[Component]], bool]


def dump_entity(
    entity: Entity,
    *,
    component_filter: Optional[ComponentFilter] = None,
) -> EntityData:
    """Dumps a single entity's components into an :data:`EntityData` mapping.

    :param entity: Entity whose components are dumped
    :param component_filter: Optional predicate; component types for which it
        returns ``False`` are skipped
    :return: Component type name -> component data
    """
    data: EntityData = {}
    for comp_type, comp in entity.iter_component_items():
        if component_filter is not None and not component_filter(comp_type):
            continue
        data[comp_type.__name__] = comp.model_dump()
    return data


def dump_components(*components: Component) -> EntityData:
    """Dumps component instances into a single :data:`EntityData` mapping.

    Convenient when building an entity's component dict outside a live context,
    e.g. blueprint definitions. Each type name maps to that component's data.

    :param components: Component instances to dump
    :return: Component type name -> component data
    """
    return {type(comp).__name__: comp.model_dump() for comp in components}


def dump_entities(
    entities: Iterable[Entity],
    *,
    component_filter: Optional[ComponentFilter] = None,
) -> ContextData:
    """Dumps entities into a name-keyed :data:`ContextData` mapping.

    Entities are keyed by :attr:`Entity.name`, so names must be non-empty and
    unique within ``entities`` (a duplicate would silently drop data).

    :param entities: Entities to dump, iterated in the desired key order
    :param component_filter: Optional predicate forwarded to :func:`dump_entity`
    :return: Entity name -> entity data
    :raises AssertionError: If an entity has an empty or duplicate name
    """
    result: ContextData = {}
    for entity in entities:
        name = entity.name
        assert name != "", f"Entity at index {entity.index} has no name."
        assert name not in result, f"Duplicate entity name: {name!r}."
        result[name] = dump_entity(entity, component_filter=component_filter)
    return result


def dump_context(
    context: Context,
    *,
    component_filter: Optional[ComponentFilter] = None,
) -> ContextData:
    """Dumps the live entities of a context, ordered by slot index.

    :param context: Context whose core is dumped
    :param component_filter: Optional predicate forwarded to :func:`dump_entity`
    :return: Entity name -> entity data
    """
    ordered = sorted(context.entities, key=lambda entity: entity.index)
    return dump_entities(ordered, component_filter=component_filter)


def load_context(
    context: Context,
    data: ContextData,
    resolve_type: ComponentResolver,
) -> Dict[str, Entity]:
    """Rebuilds a context core from a :func:`dump_context` mapping.

    The target context must be empty. Components are written straight into the
    context's storage, bypassing ``Entity.add`` so that no component events
    fire; groups and reactive processors are therefore expected to be created
    after loading.

    :param context: Empty context to populate
    :param data: Name-keyed mapping produced by :func:`dump_context`
    :param resolve_type: Resolver turning a component type name and its data
        back into a component class
    :return: Entity name -> restored entity handle
    :raises AssertionError: If the context is not empty
    """
    assert context.entity_count == 0, "load_context expects an empty context."

    restored: Dict[str, Entity] = {}
    for name, entity_data in data.items():
        entity = context.create_entity()
        entity.name = name
        restored[name] = entity

        for comp_name, comp_data in entity_data.items():
            comp_type = resolve_type(comp_name, comp_data)
            context.store_add(entity.index, comp_type, comp_type(**comp_data))

    return restored
