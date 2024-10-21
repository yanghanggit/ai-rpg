from typing import List, Any
from loguru import logger
from player.player_message import PlayerClientMessage, PlayerClientMessageTag
from my_data.model_def import AgentEvent


class PlayerProxy:

    SYSTEM_MESSAGE_SENDER = f"[system]"

    def __init__(self, name: str) -> None:
        self._name: str = name

        from player.base_command import PlayerCommand

        self._commands: List[PlayerCommand] = []

        self._client_messages: List[PlayerClientMessage] = []
        self._login_messages: List[PlayerClientMessage] = []

        self._over: bool = False

        self._ctrl_actor_name: str = ""
        self._need_show_stage_messages: bool = False
        self._need_show_actors_in_stage_messages: bool = False

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
        agent_event: AgentEvent,
        target: List[PlayerClientMessage],
    ) -> None:

        target.append(PlayerClientMessage(tag=tag, sender=sender, event=agent_event))

    ##########################################################################################################################################################
    def add_system_message(self, agent_event: AgentEvent) -> None:
        self._add_client_message(
            PlayerClientMessageTag.SYSTEM,
            PlayerProxy.SYSTEM_MESSAGE_SENDER,
            agent_event,
            self._client_messages,
        )

    ##########################################################################################################################################################
    def add_actor_message(self, actor_name: str, agent_event: AgentEvent) -> None:
        self._add_client_message(
            PlayerClientMessageTag.ACTOR,
            actor_name,
            agent_event,
            self._client_messages,
        )

    ##########################################################################################################################################################
    def add_stage_message(self, stage_name: str, agent_event: AgentEvent) -> None:
        self._add_client_message(
            PlayerClientMessageTag.STAGE,
            stage_name,
            agent_event,
            self._client_messages,
        )

    ##########################################################################################################################################################
    def add_login_message(self, actor_name: str, agent_event: AgentEvent) -> None:
        self._add_client_message(
            PlayerClientMessageTag.ACTOR,
            actor_name,
            agent_event,
            self._login_messages,
        )

    ##########################################################################################################################################################
    def send_client_messages(self, send_count: int) -> List[str]:
        ret: List[str] = []
        for client_message in self._client_messages[-send_count:]:
            json_str = client_message.model_dump_json()
            ret.append(json_str)
            logger.warning(json_str)
        return ret

    ##########################################################################################################################################################
    def on_dead(self) -> None:
        self._over = True
        logger.warning(f"{self._name} : {self._ctrl_actor_name}, 死亡了!!!!!")

    ##########################################################################################################################################################
