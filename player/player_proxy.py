from typing import List, Any
from loguru import logger


class PlayerProxy:

    def __init__(self, name: str) -> None:
        self._name: str = name

        from player.base_command import PlayerCommand

        self._commands: List[PlayerCommand] = []

        self._client_messages: List[tuple[str, str]] = []
        self._login_messages: List[tuple[str, str]] = []

    ##########################################################################################################################################################
    def add_command(self, command: Any) -> None:
        self._commands.append(command)

    ##########################################################################################################################################################
    def add_message(
        self, sender: str, message: str, target: List[tuple[str, str]]
    ) -> None:
        target.append((sender, message))

    ##########################################################################################################################################################
    def add_system_message(self, message: str) -> None:
        self.add_message(f"[system]", message, self._client_messages)

    ##########################################################################################################################################################
    def add_actor_message(self, actor_name: str, message: str) -> None:

        # 暂时先不做重复添加 todo
        for current_content in self._client_messages:
            if current_content[1] == message:
                return

        self.add_message(f"[{actor_name}]", message, self._client_messages)

    ##########################################################################################################################################################
    def add_stage_message(self, stage_name: str, message: str) -> None:
        self.add_message(f"[{stage_name}]", message, self._client_messages)

    ##########################################################################################################################################################
    def add_login_message(self, actor_name: str, message: str) -> None:
        self.add_message(f"{actor_name}", message, self._login_messages)

    ##########################################################################################################################################################
    def show_messages(self, count: int) -> None:
        for message in self._client_messages[-count:]:
            tag = message[0]
            content = message[1]
            logger.warning(f"{tag}=>{content}")
