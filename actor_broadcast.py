from stage import Stage
from npc import NPC
from player import Player
                 
def actor_broadcast(actor: Stage | NPC | Player, content:str) -> None:    
    # 使用 is not None 明确检查 actor 和 actor.stage 都不是 None
    if actor is not None and actor.stage is not None:
        enter_event = f"{actor.name} 说 {content}"
        print(f"[{actor.name}]=>", enter_event)
        actor.stage.add_memory(enter_event)
    else:
        print("actor_broadcast: actor or actor.stage is None")
        

