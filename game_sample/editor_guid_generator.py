from enum import IntEnum


class GUIDType(IntEnum):
    ACTOR_TYPE = 100000000
    STAGE_TYPE = 200000000
    PROP_TYPE = 300000000
    WORLD_SYSTEM_TYPE = 400000000


class EditorGUIDGenerator:

    def __init__(self) -> None:
        self._actor_index: int = 0
        self._stage_index: int = 0
        self._prop_index: int = 0
        self._world_system_index: int = 0

    def gen_actor_guid(
        self, name: str, base_index: GUIDType = GUIDType.ACTOR_TYPE
    ) -> int:

        self._actor_index += 1
        return base_index.value + self._actor_index

    def gen_stage_guid(
        self, name: str, base_index: GUIDType = GUIDType.STAGE_TYPE
    ) -> int:
        self._stage_index += 1
        return base_index.value + self._stage_index

    def gen_prop_guid(
        self, name: str, base_index: GUIDType = GUIDType.PROP_TYPE
    ) -> int:
        self._prop_index += 1
        return base_index.value + self._prop_index

    def gen_world_system_guid(
        self, name: str, base_index: GUIDType = GUIDType.WORLD_SYSTEM_TYPE
    ) -> int:
        self._world_system_index += 1
        return base_index.value + self._world_system_index


###
editor_guid_generator = EditorGUIDGenerator()
