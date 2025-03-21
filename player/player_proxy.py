from typing import Final, List
from loguru import logger
from tcg_models.event_models import BaseEvent
from player.player_command2 import PlayerCommand2
from tcg_models.player_notification import PlayerNotification


class PlayerProxy:

    def __init__(
        self,
        name: str,
    ) -> None:

        self._name: Final[str] = name

        self._commands: List[PlayerCommand2] = []

        self._notifications: List[PlayerNotification] = []

    # ##########################################################################################################################################################
    @property
    def name(self) -> str:
        return self._name

    ##########################################################################################################################################################
    def add_command2(self, command: PlayerCommand2) -> None:
        logger.info(f"add_player_command: {command}")
        self._commands.append(command)

    ##########################################################################################################################################################

    ##########################################################################################################################################################
    def add_notification(self, event: BaseEvent) -> None:
        # logger.debug(f"add_event: {event}")
        self._notifications.append(
            PlayerNotification(
                data=event,
            )
        )

    ##########################################################################################################################################################
