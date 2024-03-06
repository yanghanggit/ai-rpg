from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys

class BaseAgent():
    def __init__(self, name):
        self.name = name

    def connect(self, url):
        self.agent = RemoteRunnable(url)

class TaskAgent(BaseAgent):
    def __init__(self, name):
        super().__init__(name)

class StoryAgent(BaseAgent):
    def __init__(self, name):
        super().__init__(name)

class NpcAgent(BaseAgent):
    def __init__(self, name):
        super().__init__(name)

class PlayerAgent(BaseAgent):
    def __init__(self, name):
        super().__init__(name)


def main():

    task = TaskAgent("Task")
    story = StoryAgent("Story")
    npc = NpcAgent("NPC")
    player = PlayerAgent("Player")

    task.connect("http://localhost:8001/system/task/")
    story.connect("http://localhost:8002/system/story/")
    npc.connect("http://localhost:8003/actor/npc/oldman")
    player.connect("http://localhost:8004/actor/player/")

    story_history = []
    npc_history = []
    player_history = []
    story_input = ""
    npc_input = ""
    player_input = ""

    # 一位年轻的勇者偶遇一位曾经的冒险家老人,绞尽脑汁想要从老人手中获得他的神秘地图。
    brief_task = input("请输入任务简述:")

    task_response = task.agent.invoke({"brief_task":brief_task , "input": "输出一个任务。", "chat_history":[]})
    print("[任务系统]" + task_response['output'])
    print("==============================================")
    # story_input = task_response['output']
    story_response = story.agent.invoke({"input": task_response['output'], "chat_history": story_history})
    # 故事历史存入【任务内容】【故事】
    story_history.extend([HumanMessage(content=task_response['output']), AIMessage(content=story_response['output'])])
    print("[故事]" + story_response['output'])
    print("==============================================")
    #npc_input = story_response['output']
    npc_response = npc.agent.invoke({"input": story_response['output'], "chat_history": npc_history})
    # NPC历史存入【任务内容】【故事】【NPC反应】
    npc_history.extend([AIMessage(content=task_response['output']),AIMessage(content=story_response['output']),AIMessage(content=npc_response['output'])])
    print("[老人]" + npc_response['output'])
    print("==============================================")
    player_input_manual = input("[user input]: ")
    print("==============================================")
    # player_input = npc_response['output']
    player_history.append(HumanMessage(content=npc_response['output']))
    player_response = player.agent.invoke({"input": player_input_manual, "chat_history": player_history})
    # Player历史存入【任务内容】【故事】【NPC反应】【Player回应】
    player_history.extend([AIMessage(content=task_response['output']),AIMessage(content=story_response['output']),AIMessage(content=npc_response['output']),HumanMessage(content=player_input_manual), AIMessage(content=player_response['output'])])
    print("[勇者]" + player_response['output'])
    print("==============================================")
    while True:
        # story_input = player_response['output']
        story_response = story.agent.invoke({"input": player_response['output'], "chat_history": story_history})
        # 故事历史存入【NPC反应】【Player回应】【故事】
        story_history.extend([HumanMessage(content=npc_response['output']),HumanMessage(content=player_response['output']), AIMessage(content=story_response['output'])])
        print("[故事]" + story_response['output'])
        print("==============================================")

        # npc_input = story_response['output']
        npc_response = npc.agent.invoke({"input": story_response['output'], "chat_history": npc_history})
        # NPC历史存入【Player回应】【故事】【NPC反应】
        npc_history.extend([HumanMessage(content=player_response['output']),HumanMessage(content=story_response['output']),AIMessage(content=npc_response['output'])])
        print("[老人]" + npc_response['output'])
        print("==============================================")

        # player_input = npc_response['output']
        # Player历史存入【故事】【NPC反应】
        player_history.extend([AIMessage(content=story_response['output']),HumanMessage(content=npc_response['output'])])

        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            sys.exit()

        player_response = player.agent.invoke({"input": usr_input, "chat_history": player_history})
        # Player历史存入【Player回应】
        player_history.append(AIMessage(content=player_response['output']))
        print("[勇者]" + player_response['output'])
        print("==============================================")
        



if __name__ == "__main__":
    print("==============================================")
    main()