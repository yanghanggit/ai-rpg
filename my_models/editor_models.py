from enum import StrEnum, unique


@unique
class EditorEntityType(StrEnum):
    WORLD_SYSTEM = "WorldSystem"
    PLAYER = "Player"
    ACTOR = "Actor"
    STAGE = "Stage"
    ABOUT_GAME = "AboutGame"
    # ACTOR_GROUP = "ActorGroup"
    ACTOR_SPAWN = "ActorSpawn"
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
    STAGE_PROP = "stage_prop"
    STAGE_GRAPH = "stage_graph"
    ACTORS_IN_STAGE = "actors_in_stage"
    GROUPS_IN_STAGE = "groups_in_stage"
    DESCRIPTION = "description"
    SPAWN = "spawn"
    SPAWNERS_IN_STAGE = "spawners_in_stage"
