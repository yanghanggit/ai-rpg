from stage import Stage
from npc import NPC
from player import Player
       
def actor_enter_stage(actor: NPC | Player, stage: Stage) -> None:        
    if stage is None or actor is None:
        print(f"error stage:{stage}, actor:{actor}")
        return

    if actor.stage == stage:
        print(f"{actor.name}已经在{stage.name}")
        return
    
    if actor.stage is not None:
        # 这里我们已经确认 actor.stage 不是 None，所以我们可以安全地赋值
        old_stage: Stage = actor.stage
        old_stage.remove_actor(actor)
        #
        print(f"[{actor.name}]=>", f"你离开了{old_stage.name}")
        actor.add_memory(f"你离开了{old_stage.name}")
        #
        leave_event = f"""你知道了发生了如下事件：{actor.name}离开了{old_stage.name}"""
        old_stage.add_memory(leave_event)
        print("==============================================")
            
    stage.add_actor(actor)
    print(f"[{actor.name}]=>", f"你进入了{stage.name}")
    enter_event = f"""你知道了发生了如下事件：{actor.name}进入了{stage.name}, 他是{actor.profile_character}"""
    stage.add_memory(enter_event)
