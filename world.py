###
from actor import Actor
from typing import List
from stage import Stage  # 假设你有一个名为Stage的类
from typing import Optional


class World(Actor):

    def __init__(self, name:str):
        super().__init__(name)
        self.stages: List[Stage] = []

    #
    def add_stage(self, stage: Stage) -> None:
        self.stages.append(stage)
        stage.world = self
    
    #
    def get_stage(self, find_name: str) -> Optional[Stage]:
        for stage in self.stages:
            if stage.name == find_name:
                return stage
        return None

    #
    def get_actor(self, find_name: str) -> Optional[Actor]:
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
    def all_actors(self) -> List[Actor]:
        actors: List[Actor] = []
        actors.append(self)
        for stage in self.stages:
            actors.append(stage)
            for actor in stage.actors:
                actors.append(actor)
        return actors
    
    #
    def connect_all(self) -> None:
        self.connect(self.url)
        for stage in self.stages:
            stage.connect(stage.url)
            for actor in stage.actors:
                actor.connect(actor.url)

    #
    def load_all(self, prompt: str) -> None:
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

 