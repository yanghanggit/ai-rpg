from typing import Final, List
from loguru import logger
from models.event_models import BaseEvent
from player.player_command import PlayerCommand
from models.player_notification import PlayerNotification


class PlayerProxy:

    def __init__(
        self,
        name: str,
    ) -> None:

        self._name: Final[str] = name

        self._commands: List[PlayerCommand] = []

        self._notifications: List[PlayerNotification] = []

    # ##########################################################################################################################################################
    @property
    def name(self) -> str:
        return self._name

    ##########################################################################################################################################################
    def add_command(self, command: PlayerCommand) -> None:
        logger.debug(f"add_player_command: {command}")
        self._commands.append(command)

    ##########################################################################################################################################################
    def add_notification(self, event: BaseEvent) -> None:
        logger.debug(f"{self._name}, add_notification: {event}")
        self._notifications.append(
            PlayerNotification(
                data=event,
            )
        )

    ##########################################################################################################################################################
