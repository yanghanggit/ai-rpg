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
def npc_enter_scene(npc, scene, prompt):
    print(f"npc_enter_scene: {npc.name} enter {scene.name}", prompt)
    print("==============================================")

    #记录!!
    scene.actors.append(npc)

    #场景触发
    str1 = talk_to_agent(
    prompt, 
    scene.agent, scene.chat_history)

    #同步给NPC
    last_message = scene.chat_history[-1]
    message_content = last_message.content
    str2 = talk_to_agent(
        f"""
        # 当前场景状态
        - {message_content}
        # 需求
        - 关于“当前场景状态“，你需要理解（即你处于这种环境下）。
        - 请输出你的感受与想法
        """,
        npc.agent, npc.chat_history)

    return [str1, str2]

#
def item_enter_scene(item, scene, prompt):
    print(f"item_enter_scene: {item.name} enter {scene.name}", prompt)
    print("==============================================")

    #记录!!
    scene.actors.append(item)

    #场景触发
    str1 = talk_to_agent(
    prompt, 
    scene.agent, scene.chat_history)

    #同步给NPC
    last_message = scene.chat_history[-1]
    message_content = last_message.content
    str2 = talk_to_agent(
        f"""
        # 当前场景状态
        - {message_content}
        # 需求
        - 关于“当前场景状态“，你需要理解（即你处于这种环境下）。
        - 请输出你的感受与想法
        """,
        item.agent, item.chat_history)

    return [str1, str2]

#
def player_enter_scene(player, scene, prompt):
    print(f"player_enter_scene: {player.name} enter {scene.name}", prompt)
    print("==============================================")
    #记录!!
    scene.actors.append(player)
    name_list = []
    #场景触发
    str1 = talk_to_agent(
        prompt, 
        scene.agent, scene.chat_history)
    
    name_list.append(f"{scene.name}")

    #广播给场景的所有actor
    str_array = []
    for actor in scene.actors:
        if (actor == player):
            continue 

        str2 = talk_to_agent(
            prompt, 
            actor.agent, actor.chat_history)
        str_array.append(str2)
        name_list.append(f"{actor.name}")

    result = [str1] + str_array
    return [name_list, result]

#
def player_talk_to_npc(player, npc, prompt):
    str1 = talk_to_agent(
        prompt, 
        npc.agent, npc.chat_history)
    return str1


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

    #
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

    #first load！！
    print(f"[{world.name}]:", call_agent(world, "你是谁？"))
    print(f"[{stage.name}]:", call_agent(stage, f"我({player.name})用力推开了屋子的门，闯入屋子而且面色凝重，外面的寒风吹进了屋子"))
    print(f"[{npc.name}]:", call_agent(npc, "你好！"))

    # str2 = talk_to_agent(
    #     f"""
    #     你是谁？
    #     """,
    #     world.agent, world.chat_history)

    # print(f"[{world.name}]:", str2)




    # #
    # player = Player("勇者")
    # #
    # npc = NPC("卡斯帕·艾伦德")
    # npc.conncect("http://localhost:8001/actor/npc/elder/")
    # #
    # scene = Stage("小木屋")
    # scene.conncect("http://localhost:8002/actor/npc/house/")
    # #
    # map = Item("神秘地图")
    # map.conncect("http://localhost:8003/actor/npc/item/")

    # ###
    # nes_res = npc_enter_scene(npc, scene, 
    # f"""
    # # 状态
    # - 冬天的晚上，我（{npc.name}）坐在你({scene.name})的壁炉旁
    # - 暗示：我（{npc.name}）是你的主人，你的一切设施均和我有关
    # # 事件
    # - 我（{npc.name}）在沉思和回忆过往，有一些难过，并向壁炉中的火投入了一根木柴
    # # 推理规则
    # - 你可以根据“状态”与“事件”做判断与推理，并进一步延展
    # - 暗示的部分理解即可，不需要在输出文本中体现
    # # 需求
    # - 请根据“状态“，”事件“，“推理规则”与“对话规则”来输出文本（并适当润色）
    # """)
    # #
    # print(f"[{scene.name}]:", nes_res[0])
    # print(f"[{npc.name}]:", nes_res[1])
    # print("==============================================")
    # ###

    # ###
    # ies_res = item_enter_scene(map, scene, f"我({map.name})静静地躺在{scene.name}的旧箱子里，{npc.name}在最后一次冒险之后将我藏在了这里，不愿意再次面对那些痛苦的回忆")
    # print(f"[{scene.name}]:", ies_res[0])
    # print(f"[{map.name}]:", ies_res[1])
    # print("==============================================")
    # ###

    # ###
    # pes_res = player_enter_scene(player, scene, f"我({player.name})用力推开了屋子的门，闯入屋子而且面色凝重，外面的寒风吹进了屋子")
    # for i in range(len(pes_res[0])):
    #     print(f"[{pes_res[0][i]}]:", pes_res[1][i])
    # print("==============================================")
    # ###
    
    # 输入循环
    while True:
        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            sys.exit()


        # talk_content = parse_talk(usr_input)
        # print(f"[{player.name}]:", talk_content)
        # print(f"[{world.name}]:", player_talk_to_npc(player, world, talk_content))


        # elif "/talk" in usr_input:
        #     talk_content = parse_talk(usr_input)
        #     #
        #     print(f"[{player.name}]:", talk_content)
        #     print(f"[{npc.name}]:", player_talk_to_npc(player, npc, talk_content))

        # else:
        #     talk_content = parse_talk(usr_input)
        #     #
        #     print(f"[{player.name}]:", talk_content)
        #     print(f"[{npc.name}]:", player_talk_to_npc(player, npc, talk_content))
        # print("==============================================")

if __name__ == "__main__":
    print("==============================================")
    main()