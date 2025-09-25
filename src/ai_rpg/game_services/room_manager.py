# from typing import Dict, Optional
# from ..game_services.room import Room


# class RoomManager:

#     def __init__(self) -> None:
#         self._rooms: Dict[str, Room] = {}

#     ###############################################################################################################################################
#     def has_room(self, user_name: str) -> bool:
#         return user_name in self._rooms

#     ###############################################################################################################################################
#     def get_room(self, user_name: str) -> Optional[Room]:
#         return self._rooms.get(user_name, None)

#     ###############################################################################################################################################
#     def create_room(self, user_name: str) -> Room:
#         if self.has_room(user_name):
#             assert False, f"room {user_name} already exists"
#         room = Room(user_name)
#         self._rooms[user_name] = room
#         return room

#     ###############################################################################################################################################
#     def remove_room(self, room: Room) -> None:
#         user_name = room._username
#         assert user_name in self._rooms
#         self._rooms.pop(user_name, None)

#     ###############################################################################################################################################
