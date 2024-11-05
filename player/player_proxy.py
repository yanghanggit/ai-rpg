from typing import List, Any
from loguru import logger
from my_models.event_models import (
    BaseEvent,
)
from my_models.player_models import (
    PlayerClientMessage,
    PlayerClientMessageTag,
    PlayerProxyModel,
)


class PlayerProxy:

    SYSTEM_MESSAGE_SENDER = f"[system]"

    def __init__(
        self,
        player_proxy_model: PlayerProxyModel,
    ) -> None:

        self._model = player_proxy_model

        from player.base_command import PlayerCommand

        self._commands: List[PlayerCommand] = []

    ##########################################################################################################################################################
    @property
    def model(self) -> PlayerProxyModel:
        return self._model

    ##########################################################################################################################################################
    @property
    def name(self) -> str:
        return self._model.name

    ##########################################################################################################################################################
    @property
    def actor_name(self) -> str:
        return self._model.actor_name

    ##########################################################################################################################################################
    @property
    def over(self) -> bool:
        return self._model.over

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
        self._add_client_message(
            PlayerClientMessage(
                tag=PlayerClientMessageTag.ACTOR,
                sender=actor_name,
                agent_event=agent_event,
            )
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
        self.model.over = True
        logger.warning(f"{self._model.name} : {self._model.actor_name}, 死亡了!!!!!")

    ##########################################################################################################################################################
    def on_load(self) -> None:
        logger.warning(f"{self._model.name} : {self._model.actor_name}, 加载了!!!!!")

    ##########################################################################################################################################################
    # todo
    def flush_kickoff_messages(self) -> None:

        for message in self._model.cache_kickoff_messages:
            self._add_client_message(message)

        self._model.cache_kickoff_messages.clear()

    ##########################################################################################################################################################
    def cache_kickoff_message(self, actor_name: str, agent_event: BaseEvent) -> None:

        self._model.cache_kickoff_messages.append(
            PlayerClientMessage(
                tag=PlayerClientMessageTag.KICKOFF,
                sender=actor_name,
                agent_event=agent_event,
            )
        )

    ##########################################################################################################################################################
