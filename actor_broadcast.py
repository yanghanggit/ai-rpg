from actor import Actor
from stage import Stage
from npc import NPC
from player import Player
                 
def actor_broadcast(actor: Actor, content:str) -> None:        
    if actor == None:
        print("/say2everyone error1 = ", "没有找到这个玩家") 
        return
    
    broadcast_stage = None
    if  isinstance(actor, NPC) or isinstance(actor, Player):
        if actor.stage == None:
            print(f"[{actor.name}]=>", "你还没有进入任何场景")
            return
        else:
            broadcast_stage = actor.stage
    elif isinstance(actor, Stage):
        broadcast_stage = actor
    ###
    enter_event = f"""{actor.name} 说 {content}"""
    print(f"[{actor.name}]=>", enter_event)
    broadcast_stage.add_memory(enter_event)

