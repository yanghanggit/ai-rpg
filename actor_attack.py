from actor import Actor
from stage import Stage
from action import Action
from npc import NPC
from player import Player
from action import FIGHT
                 
def actor_attack(actor: Actor, target_name:str) -> Action:       
    if actor == None:
        return

    curent_stage = None
    if  isinstance(actor, NPC) or isinstance(actor, Player):
        if actor.stage == None:
            print(f"[{actor.name}]=>", "你还没有进入任何场景")
            return
        else:
            curent_stage = actor.stage
    elif isinstance(actor, Stage):
        curent_stage = actor
        
    attack_target = curent_stage.get_actor(target_name)
    if attack_target== None:  
        print(f"[{actor.name}]=>", f"在{curent_stage.name}没有找到这个人{target_name}")
        return

    if attack_target == actor:
        print(f"[{actor.name}]=>", f"你不能攻击自己")
        return
    
    actor.add_memory(f"你准备对{attack_target.name}发动攻击")
    return curent_stage, Action(actor, [FIGHT], [attack_target.name], [""], [""])


