from enum import IntEnum, StrEnum, unique


@unique
class EditorEntityType(StrEnum):
    WORLD_SYSTEM = "WorldSystem"
    PLAYER = "Player"
    ACTOR = "Actor"
    STAGE = "Stage"
    EPOCH_SCRIPT = "EpochScript"
    SPAWNER = "Spawner"
    GROUP = "Group"


@unique
class EditorProperty(StrEnum):
    TYPE = "type"
    NAME = "name"
    ATTRIBUTES = "attributes"
    KICK_OFF_MESSAGE = "kick_off_message"
    ACTOR_CURRENT_USING_PROP = "actor_current_using_prop"
    ACTOR_PROP = "actor_prop"
    STAGE_GRAPH = "stage_graph"
    ACTORS_IN_STAGE = "actors_in_stage"
    GROUPS_IN_STAGE = "groups_in_stage"
    DESCRIPTION = "description"
    SPAWN = "spawn"
    SPAWNERS_IN_STAGE = "spawners_in_stage"


@unique
class GUIDType(IntEnum):
    ACTOR_TYPE = 1 * 1000 * 1000
    STAGE_TYPE = 2 * 1000 * 1000
    PROP_TYPE = 3 * 1000 * 1000
    WORLD_SYSTEM_TYPE = 4 * 1000 * 1000
    RUNTIME_ACTOR_TYPE = 5 * 1000 * 1000
    RUNTIME_PROP_TYPE = 6 * 1000 * 1000
