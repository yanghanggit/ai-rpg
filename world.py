###
from actor import Actor

class World(Actor):

    def __init__(self, name: str):
        super().__init__(name)
        self.world = self
        self.stages = []

    #
    def add_stage(self, stage) -> None:
        self.stages.append(stage)
        stage.world = self
    
    #
    def get_stage(self, find_name: str):
        for stage in self.stages:
            if stage.name == find_name:
                return stage
        return None

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
    
    #
    def all_actors(self):
        actors = []
        actors.append(self)
        for stage in self.stages:
            actors.append(stage)
            for actor in stage.actors:
                actors.append(actor)
        return actors
    
    #
    def connect_all(self):
        self.connect(self.url)
        for stage in self.stages:
            stage.connect(stage.url)
            for actor in stage.actors:
                actor.connect(actor.url)

    #
    def load_all(self, prompt: str):
        # 世界载入
        log = self.call_agent(prompt)
        print(f"[{self.name}] load=>", log)
        print("==============================================")

        for stage in self.stages:
            #场景载入
            log = stage.call_agent(prompt)
            print(f"[{stage.name}] load=>", log)
            print("==============================================")

            for actor in stage.actors:
                log = actor.call_agent(prompt)
                print(f"[{actor.name}] load=>", log)
                print("==============================================")

 