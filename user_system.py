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
    env_script = talk_to_agent(
            f"""
#状态
-村长坐在屋子里（篝火旁）
#事件
-勇者进入了屋子
#需求
-请根据#状态与#事件，输出一段描写文字，表现此时的场景状态
            """, 
            scene_agent, scene_achat_history)
    #
    print("[scene]:", env_script)


    #
    print("[npc]:", talk_to_agent(
            f"""
#此时环境状态
-{env_script}
#要求
-根据#此时环境状态，输出一段对话，标志着村长与勇者的对话开始
            """, 
            npc_agent, npc_achat_history))

    while True:
        usr_input = input("[user input]: ")

        if "quit" in usr_input:
            sys.exit()

        elif "/talk" in usr_input:
            real_input = parse_talk(usr_input)
            print("[you]:", real_input)
            print(
                '[npc]:', talk_to_agent(real_input, npc_agent, npc_achat_history)
            )

        else:
            print("error command!")










if __name__ == "__main__":
    run_user_system()