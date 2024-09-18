from typing import List, Any, cast
from loguru import logger


class PlayerProxy:

    def __init__(self, name: str) -> None:
        self._name: str = name

        from player.base_command import PlayerCommand

        self._commands: List[PlayerCommand] = []

        self._client_messages: List[tuple[str, str]] = []
        self._delayed_show_login_messages: List[tuple[str, str]] = []

        self._over: bool = False
        self.is_message_queue_dirty = False

        self._ctrl_actor_name: str = ""
        self._need_show_stage_messages: bool = False
        self._need_show_actors_in_stage_messages: bool = False

    ##########################################################################################################################################################
    def add_command(self, command: Any) -> None:
        from player.base_command import PlayerCommand

        assert isinstance(command, PlayerCommand)
        self._commands.append(command)

    ##########################################################################################################################################################
    def add_message(
        self, sender: str, message: str, target: List[tuple[str, str]]
    ) -> None:
        self.is_message_queue_dirty = True
        target.append((sender, message))

    ##########################################################################################################################################################
    def add_system_message(self, message: str) -> None:
        self.add_message(f"[system]", message, self._client_messages)

    ##########################################################################################################################################################
    def add_actor_message(self, actor_name: str, message: str) -> None:
        self.add_message(f"[{actor_name}]", message, self._client_messages)

    ##########################################################################################################################################################
    def add_stage_message(self, stage_name: str, message: str) -> None:
        self.add_message(f"[{stage_name}]", message, self._client_messages)

    ##########################################################################################################################################################
    def add_login_message(self, actor_name: str, message: str) -> None:
        self.add_message(f"{actor_name}", message, self._delayed_show_login_messages)

    ##########################################################################################################################################################
    def show_messages(self, count: int) -> None:
        for message in self._client_messages[-count:]:
            tag = message[0]
            content = message[1]
            logger.warning(f"{tag}=>{content}")

    ##########################################################################################################################################################
    def send_messages(self, count: int) -> List[str]:
        ret: List[str] = []
        for message in self._client_messages[-count:]:
            tag = message[0]
            content = message[1]
            # logger.warning(f"{tag}=>{content}")
            ret.append(f"{tag}=>{content}")
        return ret

    ##########################################################################################################################################################
    def on_dead(self) -> None:
        self._over = True
        logger.warning(f"{self._name} : {self._ctrl_actor_name}, 死亡了!!!!!")

    ##########################################################################################################################################################
