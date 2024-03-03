from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys


def talk_to_agent(input_val, npc_agent, chat_history):
    response = npc_agent.invoke({"input": input_val, "chat_history": chat_history})
    chat_history.extend([HumanMessage(content=input_val), AIMessage(content=response['output'])])
    return response['output']

def parse_talk(input_val):
    if "/talk" in input_val:
        return input_val.split("/talk")[1].strip()
    return input_val

def run_user_system():

    #
    npc_agent = RemoteRunnable("http://localhost:8001/actor/npc/elder/")
    npc_achat_history = []

    #
    scene_agent = RemoteRunnable("http://localhost:8002/actor/npc/house/")
    scene_achat_history = []

    #
    scene_state = talk_to_agent(
            f"""
            # 状态
            - 冬天的晚上，我（长者）在你的壁炉旁
            - 我是你的主人
            # 事件
            - 我在沉思，可能是回忆年轻的是冒险经历与死去的伙伴
            - 我向壁炉中的火投入了一根木柴
            # 规则
            - 根据“状态”与“事件”输出对话。事件会改变状态。
            # 需求
            - 请根据“规则”，输出一段经过润色的文本，表现此时的场景状态
            """, 
            scene_agent, scene_achat_history)
    #
    print("[scene]:", scene_state)

    #
    event = "我(勇者)用力推开了屋子的门，闯入屋子而且面色凝重，外面的寒风吹进了屋子"
    print("[event]:", event)

    #
    print("[npc]:", talk_to_agent(
            f"""
            # 状态
            -{scene_state}
            # 事件
            -{event}
            # 规则
            - 根据“状态”与“事件”输出对话。事件会改变状态。
            # 需求
            - 请根据“规则”，输出一段对话，表现此时的场景状态
            """, 
            npc_agent, npc_achat_history))

    while True:
        usr_input = input("[user input]: ")

        if "/quit" in usr_input:
            sys.exit()

        elif "/talk" in usr_input:
            real_input = parse_talk(usr_input)
            print("[you]:", real_input)
            print(
                '[npc]:', talk_to_agent(real_input, npc_agent, npc_achat_history)
            )

        else:
            real_input = parse_talk(usr_input)
            print("[default]:", real_input)
            print(
                '[npc]:', talk_to_agent(real_input, npc_agent, npc_achat_history)
            )


if __name__ == "__main__":
    print("==============================================")
    run_user_system()