from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys
import re



FIGHT = "[fight]"
LEAVE = "[leave]"
STAY = "[stay]"

class Action:
    def __init__(self, plan):
        self.plan = plan

class Actor:
    def __init__(self, name, tags):
        self.name = name   
        self.chat_history = []  
        self.hp = 0
        self.damage = 0
        self.tags = tags

    # def connect(self, url):
    #     self.agent = RemoteRunnable(url)
        
    def make_plan(self, plan):
        return Action(plan)
    
    # def make_action(self, action):
    #     return action
        

class Plan:
    def __init__(self, action, targets, tags):
        self.action = action  
        self.targets = targets 
        self.tags = tags
    
    def str(self):
        return f"""{self.action}, {self.targets}, {self.tags}"""
#
def main():

    # str = f"""
    # [老猎人隐居的小木屋][stay]:...
    # [卡斯帕·艾伦德][stay][talk]:可能是时候再去外面看看世界了。
    # [小狗'短剑'][stay]:我想醒来，去看看卡斯帕。
    # """

    empty_stage = Actor("大草原", "特别美的大草原")

    actors = [Actor("小木屋", "可怕的小木屋"), Actor("僵尸", "吃人的僵尸"), Actor("猎人", "勇敢的猎人"), Actor("小狗", "可爱的小狗")]
    for actor in actors:
        print(actor.name)
        print(actor.tags)
        print("=======================")

    plans = [
       Plan(FIGHT, ["猎人"], "可怕的小木屋会吃掉人的腿"),
       Plan(FIGHT, ["猎人", "小狗"], "吃人的僵尸什么都吃"),
       Plan(FIGHT, ["僵尸"], "勇敢的猎人要战斗！"),
       Plan(STAY, ["小狗"], "胆小的小狗没啥用")
    ]

    for i in range(4):
        plan = plans[i]
        actor = actors[i]
        action = actor.make_plan(plan)
        print(action.plan.str())
        print("=======================")

   




    print("=======================")




    # array = [
    # "[闪电僵尸][fight][张三]:我要弄死你",
    # "[老猎人隐居的小木屋][stay]:...",
    # "[卡斯帕·艾伦德][stay][talk]:可能是时候再去外面看看世界了。",
    # "[小狗'短剑'][stay]:我想醒来，去看看卡斯帕。"
    # ]


    # """
    # - 如果你想攻击某个目标，那么你的输出格式为：“[fight][目标的名字]:...“，...代表着你本次攻击要说的话与心里活动。
    # - 如果你想保持现状，那么你的输出格式为：“[stay][talk]：...“，...代表着你本次保持现状要说的话与心里活动。
    # - 如果你想说话，那么你的输出格式为：“[stay][talk]:...“，...代表着你本次要说的话与心里活动。
    # - 如果不在以上3种情况，就输出"[stay]:...", ...仅代表着你的心里活动。
    # """

    # for ss in array:
    #     print(ss)
    #     a, b = ss.split(':')
    #     # print(a)
    #     # print(b)


    #     extracted_elements = []
    #     pattern = r"\[(.*?)\]"
    #     matches = re.findall(pattern, a)
    #     for match in matches:
    #         extracted_elements.append(f"[{match}]")
    #         #print(match)

    #     print(extracted_elements)

    #     name = extracted_elements[0]
    #     actions = extracted_elements[1:]
    #     if actions[0] == "[fight]":
    #         #action = actions[0]
    #         target = actions[1]
    #         print(f"{name}=>{target}:{b}")

    #     elif actions[0] == "[stay]" or actions[0] == "[talk]":
    #         print(f"{name}:{b}")


    #     #
    #     # name = matches[0]
    #     # print(name)

    #     # #
    #     # actions = matches[1:]
    #     # actions = [f"[{action}]" for action in actions]
    #     # print(actions)
        


    #     print("==============================================")



    # print("==============================================")

            
if __name__ == "__main__":
    print("==============================================")
    main()