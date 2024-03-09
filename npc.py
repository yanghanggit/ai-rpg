from actor import Actor
#
class NPC(Actor): 
    def __init__(self, name: str):
        super().__init__(name)
        self.stage = None
       