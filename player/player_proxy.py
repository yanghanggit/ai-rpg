from typing import List, Any
from loguru import logger
from my_models.models_def import (
    PlayerClientMessage,
    PlayerClientMessageTag,
    BaseAgentEvent,
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
    def need_show_actors_in_stage_messages(self) -> bool:
        return self._model.need_show_actors_in_stage_messages

    ##########################################################################################################################################################
    @property
    def need_show_stage_messages(self) -> bool:
        return self._model.need_show_stage_messages

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
    def _add_client_message(
        self,
        tag: str,
        sender: str,
        agent_event: BaseAgentEvent,
        target: List[PlayerClientMessage],
    ) -> None:

        target.append(
            PlayerClientMessage(tag=tag, sender=sender, agent_event=agent_event)
        )

    ##########################################################################################################################################################
    def add_system_message(self, agent_event: BaseAgentEvent) -> None:
        self._add_client_message(
            PlayerClientMessageTag.SYSTEM,
            PlayerProxy.SYSTEM_MESSAGE_SENDER,
            agent_event,
            self._model.client_messages,
        )

    ##########################################################################################################################################################
    def add_actor_message(self, actor_name: str, agent_event: BaseAgentEvent) -> None:

        self._add_client_message(
            PlayerClientMessageTag.ACTOR,
            actor_name,
            agent_event,
            self._model.client_messages,
        )

    ##########################################################################################################################################################
    def add_stage_message(self, stage_name: str, agent_event: BaseAgentEvent) -> None:
        self._add_client_message(
            PlayerClientMessageTag.STAGE,
            stage_name,
            agent_event,
            self._model.client_messages,
        )

    ##########################################################################################################################################################
    def cache_kickoff_message(
        self, actor_name: str, agent_event: BaseAgentEvent
    ) -> None:
        self._add_client_message(
            PlayerClientMessageTag.KICKOFF,
            actor_name,
            agent_event,
            self._model.cache_kickoff_messages,
        )

    ##########################################################################################################################################################
    def add_tip_message(self, sender_name: str, agent_event: BaseAgentEvent) -> None:

        self._add_client_message(
            PlayerClientMessageTag.TIP,
            sender_name,
            agent_event,
            self._model.client_messages,
        )

    ##########################################################################################################################################################
    def debug_client_messages(self, send_count: int) -> None:
        for client_message in self._model.client_messages[-send_count:]:
            json_str = client_message.model_dump_json()
            logger.warning(json_str)

    ##########################################################################################################################################################
    def fetch_client_messages(
        self, index: int, count: int
    ) -> List[PlayerClientMessage]:

        abs_count = abs(count)
        if index < 0:
            return self._model.client_messages[-abs_count:]

        return self._model.client_messages[index : index + abs_count]

    ##########################################################################################################################################################
    def on_dead(self) -> None:
        self.model.over = True
        logger.warning(f"{self._model.name} : {self._model.actor_name}, 死亡了!!!!!")

    ##########################################################################################################################################################
    # todo
    def flush_kickoff_messages(self) -> None:
        for message in self._model.cache_kickoff_messages:

            self._add_client_message(
                message.tag,
                message.sender,
                message.agent_event,
                self._model.client_messages,
            )

        self._model.cache_kickoff_messages.clear()

    ##########################################################################################################################################################
