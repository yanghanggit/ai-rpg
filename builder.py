###
### 测试与LLM无关的代码，和一些尝试
###

from world import World
from stage import Stage
from npc import NPC


#
class NPCBuilder:
    def __init__(self):
        self.data = None

    def build(self, json_data):
        self.data = json_data
    
    def __str__(self) -> str:
        return f"NPCBuilder: {self.data}"
    
    def create(self)-> NPC:
        npc = NPC(self.data['name'])
        npc.url = self.data['url']
        return npc

#
class StageBuilder:
    def __init__(self):
        self.data = None
        self.npc_builders = []

    def build(self, json_data):
       self.data = json_data
       for npc in json_data["NPCs"]:
           npc_builder = NPCBuilder()
           npc_builder.build(npc)
           self.npc_builders.append(npc_builder)

    def __str__(self) -> str:
        return f"StageBuilder: {self.data}"
    

    def create(self)-> Stage:
        stage = Stage(self.data['name'])
        stage.url = self.data['url']
        return stage
        

#
class WorldBuilder:
    def __init__(self):
        self.data = None
        self.stage_builders = []
        self.world = None  

    def build(self, json_data):
        #
        world_data = json_data["World"]
        self.data = world_data  
        #
        stages_data = world_data["Stages"]
        for stage in stages_data:
            stage_builder = StageBuilder()
            stage_builder.build(stage)
            self.stage_builders.append(stage_builder)


    def __str__(self) -> str:
        return f"WorldBuilder: {self.data}"
    

    def create(self)-> World:
        self.world = World(self.data['name'])
        self.world.url = self.data['url']    
        return self.world

    def all(self)->World:
        self.world = self.create()
        for stage_builder in self.stage_builders:
            stage = stage_builder.create()
            self.world.add_stage(stage)
            for npc_builder in stage_builder.npc_builders:
                npc = npc_builder.create()
                stage.add_actor(npc)
        return self.world

    


   
