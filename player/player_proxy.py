from typing import List, Any
from loguru import logger
from rpg_models.event_models import BaseEvent
from rpg_models.player_models import (
    PlayerClientMessage,
    PlayerClientMessageTag,
    PlayerProxyModel,
)
from pathlib import Path
from player.player_command2 import PlayerCommand2
from tcg_models.player_notification import PlayerNotification


class PlayerProxy:

    SYSTEM_MESSAGE_SENDER = f"[system]"

    def __init__(
        self,
        player_proxy_model: PlayerProxyModel,
    ) -> None:

        self._model = player_proxy_model

        from player.base_command import PlayerCommand

        self._commands: List[PlayerCommand] = []

        self._player_commands: List[PlayerCommand2] = []

        self._player_notifications: List[PlayerNotification] = []

    ##########################################################################################################################################################
    @property
    def client_messages(self) -> List[PlayerClientMessage]:
        return self._model.client_messages

    ##########################################################################################################################################################
    @property
    def player_name(self) -> str:
        return self._model.player_name

    ##########################################################################################################################################################
    @property
    def actor_name(self) -> str:
        return self._model.actor_name

    ##########################################################################################################################################################
    @property
    def is_player_dead(self) -> bool:
        return self._model.is_player_dead

    ##########################################################################################################################################################
    def set_actor(self, actor_name: str) -> None:
        self._model.actor_name = actor_name

    ##########################################################################################################################################################
    def add_command(self, command: Any) -> None:
        from player.base_command import PlayerCommand

        assert isinstance(command, PlayerCommand)
        self._commands.append(command)

    ##########################################################################################################################################################
    def _add_client_message(self, new_message: PlayerClientMessage) -> None:
        index = len(self._model.client_messages)
        new_message.index = index
        self._model.client_messages.append(new_message)

    ##########################################################################################################################################################
    def add_system_message(self, agent_event: BaseEvent) -> None:
        self._add_client_message(
            PlayerClientMessage(
                tag=PlayerClientMessageTag.SYSTEM,
                sender=PlayerProxy.SYSTEM_MESSAGE_SENDER,
                agent_event=agent_event,
            )
        )

    ##########################################################################################################################################################
    def add_actor_message(self, actor_name: str, agent_event: BaseEvent) -> None:
        # if self._should_ignore_event(agent_event):
        #     return

        self._add_client_message(
            PlayerClientMessage(
                tag=PlayerClientMessageTag.ACTOR,
                sender=actor_name,
                agent_event=agent_event,
            )
        )

    ##########################################################################################################################################################
    def _should_ignore_event(self, send_event: BaseEvent) -> bool:

        from rpg_models.event_models import (
            UpdateAppearanceEvent,
            PreStageExitEvent,
            GameRoundEvent,
            UpdateArchiveEvent,
            PostStageEnterEvent,
        )

        return (
            isinstance(send_event, UpdateAppearanceEvent)
            or isinstance(send_event, PreStageExitEvent)
            or isinstance(send_event, GameRoundEvent)
            or isinstance(send_event, UpdateArchiveEvent)
            or isinstance(send_event, PostStageEnterEvent)
        )

    ##########################################################################################################################################################
    def add_stage_message(self, stage_name: str, agent_event: BaseEvent) -> None:
        self._add_client_message(
            PlayerClientMessage(
                tag=PlayerClientMessageTag.STAGE,
                sender=stage_name,
                agent_event=agent_event,
            )
        )

    ##########################################################################################################################################################
    def add_tip_message(self, sender_name: str, agent_event: BaseEvent) -> None:
        self._add_client_message(
            PlayerClientMessage(
                tag=PlayerClientMessageTag.TIP,
                sender=sender_name,
                agent_event=agent_event,
            )
        )

    ##########################################################################################################################################################
    def log_recent_client_messages(self, send_count: int) -> None:
        abs_count = abs(send_count)
        for client_message in self._model.client_messages[-abs_count:]:
            json_str = client_message.model_dump_json()
            logger.warning(json_str)

    ##########################################################################################################################################################
    def fetch_client_messages(
        self, index: int, count: int
    ) -> List[PlayerClientMessage]:
        return self._model.client_messages[index : index + count]

    ##########################################################################################################################################################
    def on_dead(self) -> None:
        self._model.is_player_dead = True
        logger.warning(
            f"{self._model.player_name} : {self._model.actor_name}, 死亡了!!!!!"
        )

    ##########################################################################################################################################################
    def on_load(self) -> None:
        logger.warning(
            f"{self._model.player_name} : {self._model.actor_name}, 加载了!!!!!"
        )

    ##########################################################################################################################################################
    # todo
    def clear_and_send_kickoff_messages(self) -> None:

        for message in self._model.stored_kickoff_messages:
            self._add_client_message(message)

        self._model.stored_kickoff_messages.clear()

    ##########################################################################################################################################################
    def store_kickoff_message(self, actor_name: str, agent_event: BaseEvent) -> None:

        self._model.stored_kickoff_messages.append(
            PlayerClientMessage(
                tag=PlayerClientMessageTag.KICKOFF,
                sender=actor_name,
                agent_event=agent_event,
            )
        )

    ##########################################################################################################################################################
    def write_model_to_file(self, path: Path) -> int:

        try:
            dump_json = self._model.model_dump_json()
            return path.write_text(dump_json, encoding="utf-8")

        except Exception as e:
            logger.error(f"写文件失败: {path}, e = {e}")

        return -1

    ##########################################################################################################################################################
    def add_player_command(self, command: PlayerCommand2) -> None:
        logger.info(f"add_player_command: {command}")
        self._player_commands.append(command)

    ##########################################################################################################################################################

    ##########################################################################################################################################################
    def add_notification(self, event: BaseEvent) -> None:
        logger.debug(f"add_event: {event}")
        self._player_notifications.append(
            PlayerNotification(
                data=event,
            )
        )

    ##########################################################################################################################################################
