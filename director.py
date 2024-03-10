from actor import Actor
from stage import Stage
from npc import NPC
from player import Player

def normal_director_prompt(stage: Stage, movie_script: str) -> str:
    return f"""
    # 你按着我的给你的脚本来演绎过程，并适当润色让过程更加生动。
    ## 剧本如下
    - {movie_script}
    ## 步骤
    - 第1步：理解我的剧本
    - 第2步：根据剧本，完善你的故事讲述。要保证和脚本的结果一致。
    - 第3步：更新你的记忆
    ## 输出规则
    - 输出在保证语意完整基础上字符尽量少。
    """

def actor_feedback_confirm_prompt(stage: Stage, movie: str) -> str:
    actors = stage.actors
    actor_names = [actor.name for actor in actors]
    all_names = ' '.join(actor_names)
    return f"""
    # 你目睹或者参与了这一切，并更新了你的记忆
    - {movie}
    # 你能确认
    - {all_names} 都还存在。
    """


class Director:
    def __init__(self, name: str, stage: Stage):
        self.name: str = name
        self.stage: Stage = stage

    def direct(self, script: str)-> str:
        prompt = normal_director_prompt(self.stage, script)
        return self.stage.call_agent(prompt)
            
    def actor_feedback_prompt(self, movie: str)-> str:
        return actor_feedback_confirm_prompt(self.stage, movie)



