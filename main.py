from langchain_core.messages import HumanMessage, AIMessage
from langserve import RemoteRunnable
import sys



def main():
    story_agent = RemoteRunnable("http://localhost:8008/story/")
    grandpa_agent = RemoteRunnable("http://localhost:8009/actor/npc/grandapa/")

    story_history = []
    chat_to_grandpa_history = []

    print("成功进入龙与地下城世界.")

    story_response = story_agent.invoke({"input": "进入龙与地下城世界,开始探索.", "chat_history": story_history})
    story = AIMessage(content=story_response['output'])
    print("故事:" + story_response['output'])
    story_history.extend([HumanMessage(content="进入龙与地下城世界,开始探索."),story])

    grandpa_response = grandpa_agent.invoke({"input": "祖父,我想去探索村外的地下城.", "chat_history": chat_to_grandpa_history})
    print("祖父:" + grandpa_response['output'])
    grandpa = AIMessage(content=grandpa_response['output'])
    chat_to_grandpa_history.extend([HumanMessage(content="祖父,我想去探索村外的地下城."), grandpa])
    while True:
        human = input("你:")
        if "quit" in human:
            sys.exit()

        story_response = story_agent.invoke({"input": human, "chat_history": story_history})
        story = AIMessage(content=story_response['output'])
        print("故事:" + story_response['output'])
        story_history.extend([HumanMessage(content=human),story])

        grandpa_response = grandpa_agent.invoke({"input": human, "chat_history": chat_to_grandpa_history})
        print("爷爷:" + grandpa_response['output'])
        grandpa = AIMessage(content=grandpa_response['output'])
        chat_to_grandpa_history.extend([HumanMessage(content=human), grandpa])
        

        
        




if __name__ == "__main__":
    main()