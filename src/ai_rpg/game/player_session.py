from typing import Final, List
from ..models import AgentEvent, SessionMessage, MessageType


##########################################################################################################################################################
class PlayerSession:

    def __init__(
        self,
        name: str,
        actor: str,
    ) -> None:

        self._name: Final[str] = name
        self._actor: Final[str] = actor
        self._session_messages: List[SessionMessage] = []

    # ##########################################################################################################################################################
    @property
    def name(self) -> str:
        return self._name

    ##########################################################################################################################################################
    @property
    def actor(self) -> str:
        return self._actor

    ##########################################################################################################################################################
    @property
    def session_messages(self) -> List[SessionMessage]:
        return self._session_messages

    ##########################################################################################################################################################
    def add_agent_event_message(self, agent_event: AgentEvent) -> None:
        # logger.debug(
        #     f"[{self.name}:{self.actor}] = add_agent_event_message: {agent_event.model_dump_json()}"
        # )
        self._session_messages.append(
            SessionMessage(
                message_type=MessageType.AGENT_EVENT, data=agent_event.model_dump()
            )
        )

    ##########################################################################################################################################################
    def clear_messages(self) -> None:
        self._session_messages = []

    ##########################################################################################################################################################
