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
def system_administrator_talk_to_npc(system_administrator, npc, talk_content):
    prompt = f"""
    # 系统消息
    ## 来自{system_administrator}                    
    ## 内容
    - 对你说"{talk_content}"
    """
    return call_agent(npc, prompt)

#
def main():

    #
    system_administrator = "系统管理员"

    #
    player = Player("勇者")
    world_watcher = World("世界观察者")
    stage = Stage("小木屋")
    npc = NPC("卡斯帕·艾伦德")
    
    #
    # world.add_stage(stage)
    # stage.add_actor(npc)

    #
    world_watcher.conncect("http://localhost:8004/world/")
    # stage.conncect("http://localhost:8002/actor/npc/house/")
    # npc.conncect("http://localhost:8001/actor/npc/elder/")
    # player.conncect("http://localhost:8008/actor/player/")

   
    #add stage to world
    statge2world = call_agent(world_watcher, f"""
    # 系统消息
    ## 来自{system_administrator}                    
    ## 内容
    - 对你说“请启动”
    """
    )
    print(f"[{world_watcher.name}]:", statge2world)
    print("==============================================")


    game_start = False
    while True:
        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            sys.exit()
        if "/cancel" in usr_input:
            continue

        elif "/start" in usr_input:
            print("==============================================")
            continue

        elif "/world" in usr_input:
            content = parse_input(usr_input, "/world")
            print(f"[{system_administrator}]:", content)
            print(f"[{world_watcher.name}]:", system_administrator_talk_to_npc(system_administrator, world_watcher, content))
            print("==============================================")

        if not game_start:
            continue

if __name__ == "__main__":
    print("==============================================")
    main()