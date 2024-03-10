from stage import Stage
from action import Action
from npc import NPC
from player import Player
from action import FIGHT
from typing import Optional

###                 
def create_actor_attack_action(actor: Stage | NPC | Player, target_name: str) -> tuple[Optional[Stage], Optional[Action]]:       
    if actor is None:
        return None, None
    
    curent_stage = actor.stage
    if curent_stage is None:
        return None, None
    
    attack_target = curent_stage.get_actor(target_name)
    if attack_target is None:  
        print(f"[{actor.name}]=>", f"在{curent_stage.name}没有找到这个人{target_name}")
        return None, None
    
    if attack_target == actor:
        print(f"[{actor.name}]=>", f"你不能攻击自己")
        return None, None
    
    actor.add_memory(f"你准备对{attack_target.name}发动攻击")
    return curent_stage, Action(actor, [FIGHT], [attack_target.name], [""], [""])


