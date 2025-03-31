from typing import Dict, Final, List
from loguru import logger
from models.event_models import BaseEvent
from player.client_message import (
    ClientMessageHead,
    AgentEventMessage,
    MappingMessage,
    ClientMessage,
)


##########################################################################################################################################################
class PlayerProxy:

    def __init__(
        self,
        name: str,
    ) -> None:

        self._name: Final[str] = name
        self._client_messages: List[ClientMessage] = []

    # ##########################################################################################################################################################
    @property
    def name(self) -> str:
        return self._name

    ##########################################################################################################################################################
    def add_agent_event(self, event: BaseEvent) -> None:
        logger.info(f"{self._name}, add_agent_event: {event}")
        agent_event_message = AgentEventMessage(agent_event=event)
        self._client_messages.append(
            ClientMessage(
                head=ClientMessageHead.AGENT_EVENT,
                body=agent_event_message.model_dump_json(),
            )
        )

    ##########################################################################################################################################################
    def add_mapping(self, mapping: Dict[str, List[str]]) -> None:
        logger.info(f"{self._name}, add_mapping: {mapping}")
        mapping_message = MappingMessage(data=mapping)
        self._client_messages.append(
            ClientMessage(
                head=ClientMessageHead.MAPPING,
                body=mapping_message.model_dump_json(),
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
