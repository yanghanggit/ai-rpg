from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys

class World:
    def __init__(self, name):
        self.name = name
        self.stages = []

    def conncect(self, url):
        self.agent = RemoteRunnable(url)
        self.chat_history = []

    def add_stage(self, stage):
        self.stages.append(stage)

#
class Stage:

    def __init__(self, name):
        self.name = name
        self.actors = []

    def conncect(self, url):
        self.agent = RemoteRunnable(url)
        self.chat_history = []

    def add_actor(self, actor):
        self.actors.append(actor)

#
class Actor:
    def __init__(self, name):
        self.name = name

    def conncect(self, url):
        self.agent = RemoteRunnable(url)
        self.chat_history = []

#
class Player(Actor):
    def __init__(self, name):
        super().__init__(name)
        self.items = []

#
class NPC(Actor): 
    def __init__(self, name):
        super().__init__(name)

#
class Item(Actor): 
    def __init__(self, name):
        super().__init__(name)

#
def call_agent(target, prompt):
    if not hasattr(target, 'agent') or not hasattr(target, 'chat_history'):
        return None
    response = target.agent.invoke({"input": prompt, "chat_history": target.chat_history})
    target.chat_history.extend([HumanMessage(content=prompt), AIMessage(content=response['output'])])
    return response['output']

#希望这个方法仅表达talk的行为
def parse_input(input_val, split_str):
    if split_str in input_val:
        return input_val.split(split_str)[1].strip()
    return input_val

#
def player_talk_to_npc(player, npc, talk_content):
    return call_agent(npc, f"""#{player.name}对你说{talk_content}""")
#
def main():

    #
    player = Player("勇者")
    world = World("世界观察者")
    stage = Stage("小木屋")
    npc = NPC("卡斯帕·艾伦德")
    
    #
    world.add_stage(stage)
    stage.add_actor(npc)

    #
    world.conncect("http://localhost:8004/world/")
    stage.conncect("http://localhost:8002/actor/npc/house/")
    npc.conncect("http://localhost:8001/actor/npc/elder/")
    player.conncect("http://localhost:8008/actor/player/")

    #test call
    # print(f"[{world.name}]:", call_agent(world, "你见过鱼人与独角兽嘛？"))
    # print(f"[{stage.name}]:", call_agent(stage, f"({player.name})用力推开了屋子的门，闯入屋子而且面色凝重，外面的寒风吹进了屋子"))
    # print(f"[{npc.name}]:", call_agent(npc, "你好！你见过鱼人与独角兽嘛？"))
    # print(f"[{player.name}]:", call_agent(player, f"""请告诉你是谁？"""))   #/think 请告诉你是谁？

    #当作first load！！

    #load world
    print(f"[{world.name}]:", call_agent(world, "世界在你的观察下开始运行"))
    print("==============================================")

    #add stage
    stage_current = call_agent(stage, f"""[system]请介绍你自己，并且描述你的当前的状态""")
    print("stage_current:", stage_current)
    print("==============================================")

    #add stage to world
    statge2world = call_agent(world, f"""
    # 在世界添加一个场景
    ## 场景介绍                          
    - {stage.name}
    - 可以在“世界设定”里查找与之相关的信息
    ## 当前场景的状态
    - {stage_current}
    ## 需求
    - 对"场景介绍","场景的状态"理解记录加入“对话上下文”，并回复确认即可"""
    )
    print(f"[{world.name}]:", statge2world)
    print("==============================================")

    #
    npc_current = call_agent(npc, f"""[system]请介绍你自己，并且描述你的当前的状态""")
    print("npc_current:", npc_current)
    print("==============================================")

    #add npc to world
    npc2world = call_agent(world, f"""
    # 在世界添加一个NPC
    ## NPC介绍    
    - {npc.name}
    - 可以在“世界设定”里查找与之相关的信息
    ## 当前NPC的状态
    - {npc_current}
    ## 需求
    - 对"NPC介绍","当前NPC的状态"理解记录加入“对话上下文”，并回复确认即可"""
    )
    print(f"[{world.name}]:", npc2world)
    print("==============================================")

    #add npc to stage
    npc2stage = call_agent(stage, f"""
    # 在场景添加一个NPC
    - {npc.name},
    ## 当前NPC的状态
    - {npc_current}
    - {npc.name} 是你的主人，你的一切设施均和{npc.name} 有关
    ## 当前NPC的介绍
    - {npc_current}
    ## 当前NPC的行为
    - 冬天的晚上，（{npc.name}）坐在你({stage.name})的壁炉旁
    - （{npc.name}）在沉思和回忆过往，有一些难过，并向壁炉中的火投入了一根木柴
    ## 需求
    - 根据上下文建立与（{npc.name}）的关系
    - 理解“当前NPC的状态”，“当前NPC的介绍”,"当前NPC的行为",你需要理解，推断。
    - 以第3人称输出描述此时场景状态的文本（适当润色）
    """
    )
    print(f"[{stage.name}]:", npc2stage)
    print("==============================================")

    #stage broadcast npc
    stage2npc = call_agent(npc, f"""
        # 当前场景的状态描写
        - {npc2stage},
        ## 需求
        - 需要你理解“当前场景的状态描写记录并回复确认即可”。
        """
        )
    print(f"[{npc.name}]:", stage2npc)
    print("==============================================")


    game_start = False

    # 输入循环
    while True:
        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            sys.exit()
        if "/cancel" in usr_input:
            continue

        elif "/start" in usr_input:
            game_start = True
            stage.add_actor(player)

            #add player to world
            player2world = call_agent(world, f"""{player.name}是用户，加入了这个世界，回复确认即可"""
            )
            print(f"[{world.name}]:", player2world)
            print("==============================================")

            #add npc to stage
            player2stage = call_agent(stage, f"""
            # 事件
            - {player.name}进入了{stage.name}。用力推开了门，闯入屋子而且面色凝重，外面的寒风吹进了屋子
            ## 需求
            - 以第3人称输出文本（适当润色）
            """
            )
            print(f"[{stage.name}]:", player2stage)
            print("==============================================")

            for actor in stage.actors:
                if (actor == player):
                    continue 
                broadcast_event = call_agent(
                    actor, 
                    f"""
                    # 场景事件
                    - {player2stage},
                    ## 需求
                    - 理解“场景事件”更新你的逻辑状态
                    - 以第1人称输出你的对话文本
                    - 不要输出心里描写
                    """
                    )
                print(f"[{actor.name}]:", broadcast_event)
                print("==============================================")

            continue

        if not game_start:
            continue

        if "/talk" in usr_input:
            talk_content = parse_input(usr_input, "/talk")
            #
            print(f"[{player.name}]:", talk_content)
            print(f"[{npc.name}]:", player_talk_to_npc(player, npc, talk_content))
            print("==============================================")

        elif "/stage" in usr_input:
            talk_content = parse_input(usr_input, "/stage")
            #
            print(f"[{player.name}]:", talk_content)
            print(f"[{stage.name}]:", player_talk_to_npc(player, stage, talk_content))
            print("==============================================")

        elif "/world" in usr_input:
            talk_content = parse_input(usr_input, "/world")
            #
            print(f"[{player.name}]:", talk_content)
            print(f"[{world.name}]:", player_talk_to_npc(player, world, talk_content))
            print("==============================================")
        
        else:
            talk_content = parse_input(usr_input, "/what")
            print(f"[{player.name}]:", talk_content)

            #
            talk_to_npc_res = player_talk_to_npc(player, npc, talk_content)
            print(f"[{npc.name}]:", talk_to_npc_res)
            
            #
            syn2player = call_agent(
                    player, 
                    f"""
                    # 事件
                    - /listen {npc.name} 对你说: {talk_to_npc_res}
                    """
                    )
            print(f"[{player.name}]:", syn2player)
            print("==============================================")

if __name__ == "__main__":
    print("==============================================")
    main()