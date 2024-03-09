from actor import Actor
from stage import Stage
from action import Action
from make_plan import MakePlan
from director import Director
from stage_events import StageEvents
       
     
#### 待重构！！！！！！！！！！！！！！            
def run_stage(current_stage: Stage, players_plans: list[Action]) -> None:        
    
    #制作计划
    make_plan = MakePlan(current_stage)
    make_plan.make_all_npcs_plan()
    make_plan.make_stage_paln()
    make_plan.add_players_plan(players_plans)
    if len(make_plan.actions) == 0:
        print(f"{current_stage.name}目前没有行动与计划")
        return

    ##记录发生的事
    #movie_script: list[str] = []
    stage_events = StageEvents(current_stage.name)
    ###谁想离开？
    who_wana_leave = make_plan.who_wana_leave()
    ###谁死了
    who_is_dead: list[Actor] = []
    ###创建一个导演
    director = Director("测试的导演", current_stage)

    print("++++++++++++++++++++++++++++++++++++++++ 所有人允许说话 ++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    for action in make_plan.actions:
        if (len(action.say) > 0):
            stage_events.add_event(f"{action.planer.name}说：{action.say[0]}")

    print("+++++++++++++++++++++++++++++++++++++ 处理战斗 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    fight_actions = make_plan.get_fight_actions()
    if len(fight_actions) > 0:
        stage_events.add_event("发生了战斗！")
        #
        for action in fight_actions:
            print(f"fight action: {action}")
            stage_events.add_event(f"{action.planer.name}对{action.targets}发动了攻击")
            for target_name in action.targets:
                target = current_stage.get_actor(target_name)
                if target == None:
                    continue
                #被攻击不能走
                if target in who_wana_leave:
                    who_wana_leave.remove(target) 
                #最简单战斗计算
                target.hp -= action.planer.damage    
                stage_events.add_event(f"{action.planer.name}对{action.targets}产生了{action.planer.damage}点伤害")
                if target.hp <= 0:
                    who_is_dead.append(target)
                    stage_events.add_event(f"{target.name}已经死亡")
                else:
                    #print(f"{target.name}剩余{target.hp/target.max_hp*100}%血量")
                    pass
                print("-------------------------------------------------------------------------")

    print("+++++++++++++++++++++++++++++++++++++++ 处理战斗结果，死了的 +++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    for actor in who_is_dead:
        actor.stage.remove_actor(actor)
        stage_events.add_event(f"{actor.name}死了，离开了这个世界")

    ##处理离开的
    print("++++++++++++++++++++++++++++++++++++++++ 脱离本场景的 ++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    for actor in who_wana_leave:
        actor.stage.remove_actor(actor)
        stage_events.add_event(f"{actor.name}离开了{current_stage.name}")
        
    print("++++++++++++++++++++++++++++++++++++ 最后组装剧本 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    all_stage_events = stage_events.combine_events()
    if len(all_stage_events) == 0:
        print(f"{current_stage.name}剧本为空，说明没有任何事发生，更新状态即可")
        all_stage_events = "剧本为空，说明没有任何事发生，你更新状态即可"
    #
    print(f"++++++++++++++++++++++++++++++++++++ {current_stage.name} 场景开始演绎剧本, 结束后所有npc需要确认 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    movie = director.direct(all_stage_events)
    print(f"movie >>", movie)
    new_stage_state = current_stage.call_agent(movie)
    print(f"[{current_stage.name}]>", new_stage_state)
    for actor in current_stage.actors:
        feedback = director.actor_feedback(new_stage_state, movie)
        print(f"[{actor.name}]>" + actor.call_agent(feedback))   

    print("++++++++++++++++++++++++++++++++++最后处理离开或者战斗中逃跑的人，去往某个场景（必须知道场景名字），此时他们已经脱离本场景++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    for actor in who_wana_leave:
        stage_name = make_plan.get_actor_leave_target_stage(actor)
        if stage_name == "":
            print(f"{actor.name} 想要离开，但是不知道去哪里")
            continue

        print(f"{actor.name} 想要去{stage_name}")   
        target_stage = current_stage.world.get_stage(stage_name)
        if target_stage == None:
            print(f"{actor.name} 想要去{action.targets[0]}，但是数据上看没有这个地方！")
            continue
        ###移动
        target_stage.add_actor(actor)
        print(f"{actor.name} 到达了 {target_stage.name}")
        enter_event = f"""你知道了发生了如下事件：{actor.name}进入了{target_stage.name}"""
        target_stage.add_memory(enter_event)
    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

