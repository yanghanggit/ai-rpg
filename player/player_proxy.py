from typing import List, Optional


### 简单的类定义，后续再加
class PlayerProxy:

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._input_commands: List[str] = []
        self._client_messages: List[tuple[str, str]] = []
        self._cache_messages: List[tuple[str, str]] = []

    def add_message(
        self, sender: str, message: str, target: List[tuple[str, str]]
    ) -> None:
        target.append((sender, message))

    def add_system_message(self, message: str) -> None:
        self.add_message(f"[system]", message, self._client_messages)

    def add_actor_message(self, actor_name: str, message: str) -> None:
        self.add_message(f"[{actor_name}]", message, self._client_messages)

    def add_stage_message(self, stage_name: str, message: str) -> None:
        self.add_message(f"[{stage_name}]", message, self._client_messages)

    def add_login_message(self, actor_name: str, message: str) -> None:
        self.add_message(f"[{actor_name}]", message, self._cache_messages)


##########################################################################################################################################################
##########################################################################################################################################################
##########################################################################################################################################################
