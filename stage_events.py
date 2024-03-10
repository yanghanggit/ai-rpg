
# This class is used to store the events that occur in a stage.
       
class StageEvents():
    def __init__(self, name:str)->None:
        self.name = name
        self.events:list[str] = []

    def add_event(self, event: str) -> None:
        self.events.append(event)
        print(f"{self.name}?", event)

    def combine_events(self) -> str:
        return "\n".join(self.events)