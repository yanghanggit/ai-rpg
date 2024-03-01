from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys

def main():
    story_agent = RemoteRunnable("http://localhost:8008/story/")
    grandpa_agent = RemoteRunnable("http://localhost:8009/actor/npc/grandapa/")
    evaluate_agent = RemoteRunnable("http://localhost:8007/system/evaluate/")

    story_history = []
    chat_to_grandpa_history = []
    total_courage = 0
    background_story = ""

    print("成功进入龙与地下城世界.")

    story_response = story_agent.invoke({"input": "进入龙与地下城世界,开始探索.", "chat_history": story_history})
    story = AIMessage(content=story_response['output'])
    story_history.extend([HumanMessage(content="进入龙与地下城世界,开始探索."), story])
    background_story.join("背景故事:" + story_response['output'])

    grandpa_response = grandpa_agent.invoke({"input": "祖父,我想去探索村外的地下城."
                                             , "background_story": background_story
                                             , "chat_history": chat_to_grandpa_history})
    grandpa = AIMessage(content=grandpa_response['output'])
    chat_to_grandpa_history.extend([HumanMessage(content="祖父,我想去探索村外的地下城."), grandpa])

    print("故事:" + story_response['output'])
    print("\n祖父:" + grandpa_response['output'])

    while True:
        human = input("你:")
        if "quit" in human:
            sys.exit()

        story_response = story_agent.invoke({"input": human, "chat_history": story_history})
        story = AIMessage(content=story_response['output'])
        story_history.extend([HumanMessage(content=human),story])
        background_story.join(story_response['output'])

        
        grandpa_response = grandpa_agent.invoke({"input": human
                                                 , "background_story": background_story
                                                 , "chat_history": chat_to_grandpa_history})
        grandpa = AIMessage(content=grandpa_response['output'])
        chat_to_grandpa_history.extend([HumanMessage(content=human), grandpa])

        courage_response = evaluate_agent.invoke({"input": human})
        courage = courage_response['output']
        if (type(courage) == int):
            total_courage += courage 
        else:
            total_courage += 0

        print("故事:" + story_response['output'])
        print("\n祖父:" + grandpa_response['output'])
        print(f"当前勇气值是{total_courage}")
        

        
        




if __name__ == "__main__":
    main()