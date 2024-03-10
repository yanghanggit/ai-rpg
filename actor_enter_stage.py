from actor import Actor
from stage import Stage
from action import Action
from make_plan import MakePlan
from director import Director
from stage_events import StageEvents
from world import World
       
def actor_enter_stage(actor:Actor, stage:Stage)->bool:        
    if stage == None or actor == None:
        print(f"error stage:{stage}, actor:{actor}")
        return False
    
    if isinstance(actor, Stage) or isinstance(actor, World):
       print(f"{actor.name}是一个舞台或者世界，不能进入其他舞台")
       return False

    if actor.stage == stage:
        print(f"{actor.name}已经在{stage.name}")
        return False
    
    if actor.stage != None:
        old_stage = actor.stage
        old_stage.remove_actor(actor)
        print(f"[{actor.name}]=>", f"你离开了{old_stage.name}")
        leave_event = f"""你知道了发生了如下事件：{actor.name}离开了{old_stage.name}"""
        old_stage.add_memory(leave_event)
        print("==============================================")
    #
    stage.add_actor(actor)
    print(f"[{actor.name}]=>", f"你进入了{stage.name}")
    enter_event = f"""你知道了发生了如下事件：{actor.name}进入了{stage.name}, 他是{actor.profile_character}"""
    stage.add_memory(enter_event)
    

