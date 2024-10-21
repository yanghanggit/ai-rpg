from typing import List, Any
from loguru import logger
from player.player_message import PlayerClientMessage, PlayerClientMessageTag
from my_data.model_def import BaseAgentEvent
from pydantic import BaseModel


class PlayerProxyModel(BaseModel):
    name: str = ""
    client_messages: List[PlayerClientMessage] = []
    cache_kickoff_messages: List[PlayerClientMessage] = []
    over: bool = False
    ctrl_actor_name: str = ""
    need_show_stage_messages: bool = False
    need_show_actors_in_stage_messages: bool = False


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
    def ctrl_actor_name(self) -> str:
        return self._model.ctrl_actor_name

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
    def ctrl_actor(self, actor_name: str) -> None:
        self._model.ctrl_actor_name = actor_name

    ##########################################################################################################################################################
    def add_command(self, command: Any) -> None:
        from player.base_command import PlayerCommand

        assert isinstance(command, PlayerCommand)
        self._commands.append(command)

    ##########################################################################################################################################################
    def _add_client_message(
        self,
        tag: PlayerClientMessageTag,
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
    def remove_tip_message(self) -> None:
        self._model.client_messages = [
            message
            for message in self._model.client_messages
            if message.tag != PlayerClientMessageTag.TIP
        ]

    ##########################################################################################################################################################
    def send_client_messages(self, send_count: int) -> List[str]:
        ret: List[str] = []
        for client_message in self._model.client_messages[-send_count:]:
            json_str = client_message.model_dump_json()
            ret.append(json_str)
            logger.warning(json_str)
        return ret

    ##########################################################################################################################################################
    def on_dead(self) -> None:
        self.model.over = True
        logger.warning(
            f"{self._model.name} : {self._model.ctrl_actor_name}, 死亡了!!!!!"
        )

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
