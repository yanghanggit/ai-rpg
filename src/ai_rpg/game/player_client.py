from typing import Final, List
from loguru import logger
from ..models import AgentEvent, ClientMessage, MessageType


##########################################################################################################################################################
class PlayerClient:

    def __init__(
        self,
        name: str,
        actor: str,
    ) -> None:

        self._name: Final[str] = name
        self._actor: Final[str] = actor
        self._client_messages: List[ClientMessage] = []

    # ##########################################################################################################################################################
    @property
    def name(self) -> str:
        return self._name

    ##########################################################################################################################################################
    @property
    def actor(self) -> str:
        return self._actor

    ##########################################################################################################################################################
    def add_agent_event_message(self, agent_event: AgentEvent) -> None:
        assert self.actor != ""
        assert self.name != ""
        logger.debug(
            f"[{self.name}:{self.actor}] = add_agent_event_message: {agent_event.model_dump_json()}"
        )
        self._client_messages.append(
            ClientMessage(
                message_type=MessageType.AGENT_EVENT, data=agent_event.model_dump()
            )
        )

    ##########################################################################################################################################################
    def clear_messages(self) -> None:
        self._client_messages = []

    ##########################################################################################################################################################
    @property
    def client_messages(self) -> List[ClientMessage]:
        return self._client_messages

    ##########################################################################################################################################################
