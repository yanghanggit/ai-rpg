"""测试副本房间 code_name 的生成与透传。

覆盖范围：
- DungeonRoomData / DungeonRoomBlueprint 的 code_name 字段
- GenerateDungeonRoomsSystem._validate_room_code_names 校验逻辑
"""

from src.ai_rpg.models.dungeon_generation import (
    DungeonRoomBlueprint,
    DungeonRoomData,
)
from src.ai_rpg.systems.generate_dungeon_rooms_system import (
    _validate_room_code_names,
)


############################################################################################################
# 数据模型字段
############################################################################################################
class TestDungeonRoomCodeNameField:
    def test_room_data_code_name_defaults_empty(self) -> None:
        room = DungeonRoomData(room_type="opening")

        assert room.code_name == ""

    def test_room_blueprint_code_name_defaults_empty(self) -> None:
        room_bp = DungeonRoomBlueprint(room_type="opening")

        assert room_bp.code_name == ""

    def test_room_blueprint_code_name_serialization_round_trip(self) -> None:
        room_bp = DungeonRoomBlueprint(
            room_type="combat",
            room_name="房间.破败殿前",
            code_name="shrine_courtyard",
        )

        restored = DungeonRoomBlueprint.model_validate(room_bp.model_dump())

        assert restored.code_name == "shrine_courtyard"


############################################################################################################
# _validate_room_code_names
############################################################################################################
class TestValidateRoomCodeNames:
    def test_valid_unique_code_names_pass(self) -> None:
        rooms = [
            DungeonRoomData(
                room_type="opening",
                room_name="房间.入口",
                code_name="shrine_entrance",
            ),
            DungeonRoomData(
                room_type="combat",
                room_name="房间.破败殿前",
                code_name="shrine_courtyard",
            ),
        ]

        assert _validate_room_code_names(rooms) is None

    def test_empty_code_name_returns_error(self) -> None:
        rooms = [
            DungeonRoomData(
                room_type="opening",
                room_name="房间.入口",
                code_name="",
            )
        ]

        assert _validate_room_code_names(rooms) is not None

    def test_non_identifier_code_name_returns_error(self) -> None:
        rooms = [
            DungeonRoomData(
                room_type="opening",
                room_name="房间.入口",
                code_name="shrine entrance",
            )
        ]

        assert _validate_room_code_names(rooms) is not None

    def test_duplicate_code_name_returns_error(self) -> None:
        rooms = [
            DungeonRoomData(
                room_type="opening",
                room_name="房间.A",
                code_name="same_room",
            ),
            DungeonRoomData(
                room_type="combat",
                room_name="房间.B",
                code_name="same_room",
            ),
        ]

        assert _validate_room_code_names(rooms) is not None
