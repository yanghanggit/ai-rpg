from typing import Final, List
from loguru import logger
from models_v_0_0_1 import ClientMessageHead, ClientMessage, AgentEvent


##########################################################################################################################################################
class PlayerProxy:

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
    def add_agent_event(self, agent_event: AgentEvent) -> None:
        assert self.actor != ""
        assert self.name != ""
        logger.info(
            f"[{self.name}:{self.actor}] = add_agent_event: {agent_event.model_dump_json()}"
        )
        self._client_messages.append(
            ClientMessage(
                head=ClientMessageHead.AGENT_EVENT,
                body=agent_event.model_dump_json(),
            )
        )

    ##########################################################################################################################################################
    def clear_client_messages(self) -> None:
        logger.info(f"{self._name}, clear_client_messages")
        self._client_messages = []

    ##########################################################################################################################################################
    @property
    def client_messages(self) -> List[ClientMessage]:
        return self._client_messages

    ##########################################################################################################################################################
