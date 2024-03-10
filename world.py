from actor import Actor

class World(Actor):
    def __init__(self, name: str):
        super().__init__(name)
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
            stage.connect(self.url)
            for actor in stage.actors:
                actor.connect(self.url)

    #
    def load_all(self, prompt: str):
        log = self.call_agent(prompt)
        print(f"[{self.name}]:", log)
        print("==============================================")
        for stage in self.stages:
            stage.stage_load(prompt)
        print("==============================================")
        for stage in self.stages:
            for actor in stage.actors:
                actor.actor_load(prompt)
        print("==============================================")
        print("==============================================")
        print("==============================================")