from typing import Dict, Final, List
from loguru import logger
from models.event_models import BaseEvent
from player.client_message import (
    ClientMessageType,
    AgentEventMessage,
    MappingMessage,
    BaseClientMessage,
)


##########################################################################################################################################################
class PlayerProxy:

    def __init__(
        self,
        name: str,
    ) -> None:

        self._name: Final[str] = name
        self._client_messages: List[BaseClientMessage] = []

    # ##########################################################################################################################################################
    @property
    def name(self) -> str:
        return self._name

    ##########################################################################################################################################################
    def add_agent_event(self, event: BaseEvent) -> None:
        logger.info(f"{self._name}, add_agent_event: {event}")
        self._client_messages.append(
            AgentEventMessage(type=ClientMessageType.AGENT_EVENT, agent_event=event)
        )

    ##########################################################################################################################################################
    def add_mapping(self, mapping: Dict[str, List[str]]) -> None:
        logger.info(f"{self._name}, add_mapping: {mapping}")
        self._client_messages.append(
            MappingMessage(type=ClientMessageType.MAPPING, mapping=mapping)
        )
        
    ##########################################################################################################################################################
    def clear_client_messages(self) -> None:
        logger.info(f"{self._name}, clear_client_messages")
        self._client_messages = []

    ##########################################################################################################################################################
    @property
    def client_messages(self) -> List[BaseClientMessage]:
        return self._client_messages

    ##########################################################################################################################################################
