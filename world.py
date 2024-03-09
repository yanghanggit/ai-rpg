from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
from actor import Actor

class World(Actor):
    def __init__(self, name: str):
        super().__init__(name)
        self.stages = []

    def add_stage(self, stage) -> None:
        self.stages.append(stage)

    #
    def get_actor(self, find_name: str) -> Actor:
        if find_name == self.name:
            return self
        stages = self.stages
        for stage in stages:
            if find_name == stage.name:
                return stage
            for actor in stage.actors:
                if find_name == actor.name:
                    return actor
        return None
    

    def all_actors(self):
        actors = []
        actors.append(self)
        for stage in self.stages:
            actors.append(stage)
            for actor in stage.actors:
                actors.append(actor)
        return actors