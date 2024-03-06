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
   
    #start world
    world_watcher = World("世界观察者")
    world_watcher.conncect("http://localhost:8004/world/")
    log = system_administrator_talk_to_npc(system_administrator, world_watcher, "启动")
    print(f"[{world_watcher.name}]:", log)
    print("==============================================")

    #
    old_hunter = NPC("卡斯帕·艾伦德")
    old_hunter.conncect("http://localhost:8021/actor/npc/old_hunter/")
    log = system_administrator_talk_to_npc(system_administrator, old_hunter, "启动")
    print(f"[{old_hunter.name}]:", log)
    print("==============================================")

    #
    old_hunters_dog = NPC("小狗'短剑'")
    old_hunters_dog.conncect("http://localhost:8023/actor/npc/old_hunters_dog/")
    log = system_administrator_talk_to_npc(system_administrator, old_hunters_dog, "启动")
    print(f"[{old_hunters_dog.name}]:", log)
    print("==============================================")

    #
    old_hunters_cabin = Stage("老猎人隐居的小木屋")
    old_hunters_cabin.conncect("http://localhost:8022/stage/old_hunters_cabin/")
    log = system_administrator_talk_to_npc(system_administrator, old_hunters_cabin, "启动")
    print(f"[{old_hunters_cabin.name}]:", log)
    print("==============================================")


    #
    while True:
        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            sys.exit()
        if "/cancel" in usr_input:
            continue

        elif "/start" in usr_input:
            print("==============================================")
            continue

        elif "/1" in usr_input:
            content = parse_input(usr_input, "/1")
            print(f"[{system_administrator}]:", content)
            print(f"[{world_watcher.name}]:", system_administrator_talk_to_npc(system_administrator, world_watcher, content))
            print("==============================================")

        elif "/2" in usr_input:
            content = parse_input(usr_input, "/2")
            print(f"[{system_administrator}]:", content)
            print(f"[{old_hunter.name}]:", system_administrator_talk_to_npc(system_administrator, old_hunter, content))
        
        elif "/3" in usr_input:
            content = parse_input(usr_input, "/3")
            print(f"[{system_administrator}]:", content)
            print(f"[{old_hunters_cabin.name}]:", system_administrator_talk_to_npc(system_administrator, old_hunters_cabin, content))
        
        elif "4" in usr_input:
                content = parse_input(usr_input, "/4")
                print(f"[{system_administrator}]:", content)
                print(f"[{old_hunters_dog.name}]:", system_administrator_talk_to_npc(system_administrator, old_hunters_dog, content))


if __name__ == "__main__":
    print("==============================================")
    main()