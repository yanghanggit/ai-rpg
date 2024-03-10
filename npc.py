from actor import Actor
from rpg import RPG

#
class NPC(Actor, RPG): 
    def __init__(self, name: str):
        Actor.__init__(self, name)  # 显式地初始化Actor基类
        RPG.__init__(self)          # 显式地初始化RPG基类
        self.stage = None       