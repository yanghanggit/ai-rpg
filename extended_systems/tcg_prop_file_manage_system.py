# from typing import Final, final, Dict, List
# from models.tcg_models import PropInstance, PropPrototype


# # TCG 游戏用的道具文件管理系统！！！！！！！！！！！！！！


# @final
# class PropFile:

#     def __init__(
#         self,
#         prop_instance: PropInstance,
#         prop_prototype: PropPrototype,
#     ) -> None:
#         #
#         self._prop_instance: Final[PropInstance] = prop_instance
#         self._prop_prototype: Final[PropPrototype] = prop_prototype

#     ############################################################################################################
#     @property
#     def name(self) -> str:
#         return self._prop_instance.name

#     ############################################################################################################
#     @property
#     def guid(self) -> int:
#         return self._prop_instance.guid

#     ############################################################################################################
#     @property
#     def count(self) -> int:
#         return self._prop_instance.count

#     ############################################################################################################
#     @property
#     def details(self) -> str:
#         return self._prop_prototype.details

#     ############################################################################################################
#     @property
#     def appearance(self) -> str:
#         return self._prop_prototype.appearance

#     ############################################################################################################
#     @property
#     def insight(self) -> str:
#         return self._prop_prototype.insight

#     ############################################################################################################
#     @property
#     def type(self) -> str:
#         return self._prop_prototype.type

#     ############################################################################################################
#     @property
#     def attributes(self) -> List[int]:
#         return self._prop_instance.attributes

#     ############################################################################################################
#     @property
#     def code_name(self) -> str:
#         return self._prop_prototype.code_name

#     ############################################################################################################


# ############################################################################################################


# ############################################################################################################
# ############################################################################################################
# ############################################################################################################
# @final
# class PropFileManageSystem:

#     def __init__(self) -> None:
#         self._prop_file_mapping: Dict[str, List[PropFile]] = {}

#     ############################################################################################################
#     def clear(self) -> None:
#         self._prop_file_mapping.clear()

#     ############################################################################################################
#     def add_file(self, name: str, prop_file: PropFile) -> None:

#         if name not in self._prop_file_mapping:
#             self._prop_file_mapping[name] = []

#         if prop_file not in self._prop_file_mapping[name]:
#             self._prop_file_mapping[name].append(prop_file)

#     ############################################################################################################
