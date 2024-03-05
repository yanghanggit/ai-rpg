from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys

#希望这个方法仅表达talk的行为
def talk_to_agent(input_val, npc_agent, chat_history):
    response = npc_agent.invoke({"input": input_val, "chat_history": chat_history})
    chat_history.extend([HumanMessage(content=input_val), AIMessage(content=response['output'])])
    return response['output']

#希望这个方法仅表达talk的行为
def parse_talk(input_val):
    if "/talk" in input_val:
        return input_val.split("/talk")[1].strip()
    return input_val


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
    return talk_to_agent(
        prompt, 
        target.agent, target.chat_history)

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

    #test call
    # print(f"[{world.name}]:", call_agent(world, "你见过鱼人与独角兽嘛？"))
    # print(f"[{stage.name}]:", call_agent(stage, f"我({player.name})用力推开了屋子的门，闯入屋子而且面色凝重，外面的寒风吹进了屋子"))
    # print(f"[{npc.name}]:", call_agent(npc, "你好！你见过鱼人与独角兽嘛？"))

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
    # 关于我
    - 我是{stage.name}，你可以在“世界设定”里查找与我相关的信息
    # 我当前的状态
    - {stage_current}
    # 需求
    - 请根据"关于我","我当前的状态"，你需要理解并确认，并回复确认即可"""
    )
    print(f"[{world.name}]:", statge2world)
    print("==============================================")

    #
    npc_current = call_agent(npc, f"""[system]请介绍你自己，并且描述你的当前的状态""")
    print("npc_current:", npc_current)
    print("==============================================")

    #add npc to world
    npc2world = call_agent(world, f"""
    # 关于我
    - 我是{npc.name}，你可以在“世界设定”里查找与我相关的信息
    # 我当前的状态
    - {npc_current}
    # 需求
    - 请根据"关于我", “我当前的状态“，你需要理解并确认，并回复确认即可
    """
    )
    print(f"[{world.name}]:", npc2world)
    print("==============================================")

    #add npc to stage
    npc2stage = call_agent(stage, f"""
    # 关于我
    - 我是{npc.name},
    - 我的介绍：{npc_current},
    - 我是你的主人，你的一切设施均和我有关
    # 我在做什么
    - 冬天的晚上，我（{npc.name}）坐在你({stage.name})的壁炉旁
    - 我（{npc.name}）在沉思和回忆过往，有一些难过，并向壁炉中的火投入了一根木柴
    # 需求
    - 请建立我们之间的关系
    - 理解“关于我”，“我在做什么”, 你需要理解并回复确认即可
    """
    )
    print(f"[{stage.name}]:", npc2stage)
    print("==============================================")

    #stage broadcast npc
    stage2npc = call_agent(npc, f"""
        # 当前的场景描述
        - {npc2stage},
        - 如果出现了你的名字，就代表是你
        # 需求
        - 需要你理解“当前的场景描述”做推理和做出合理的行为与反应，并输出文本。
        """
        )
    print(f"[{npc.name}]:", stage2npc)
    print("==============================================")


    # 输入循环
    while True:
        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            sys.exit()

        elif "/start" in usr_input:
            stage.add_actor(player)

            #add player to world
            player2world = call_agent(world, f"""[system]我是{player.name}，我是用户，请确认"""
            )
            print(f"[{world.name}]:", player2world)
            print("==============================================")

            #add npc to stage
            player2stage = call_agent(stage, f"""
            # 关于我
            - 我是{player.name},
            # 事件
            - 我({player.name})用力推开了屋子的门，闯入屋子而且面色凝重，外面的寒风吹进了屋子
            # 需求
            - 请建立我们之间的关系
            - 理解“关于我”，“事件”来更新你的状态并输出文本
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
                    # 发生了事件场景状态发生更新
                    - {player2stage},
                    # 需求
                    - 请建立我们之间的关系
                    - 理解“发生了事件场景状态发生更新”来更新你的状态并输出文本"""
                    )
                print(f"[{actor.name}]:", broadcast_event)
                print("==============================================")


        elif "/talk" in usr_input:
            talk_content = parse_talk(usr_input)
            #
            print(f"[{player.name}]:", talk_content)
            print(f"[{npc.name}]:", call_agent(npc, talk_content))
            print("==============================================")
        else:
            talk_content = parse_talk(usr_input)
            print(f"[{player.name}]:", talk_content)
            print(f"[{npc.name}]:", call_agent(npc, talk_content))
            print("==============================================")

if __name__ == "__main__":
    print("==============================================")
    main()