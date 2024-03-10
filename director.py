from actor import Actor
from stage import Stage

def normal_director(stage, movie_script):
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

def actor_feedback_confirm(actor, new_stage_state, movie):
    stage = actor.stage
    actors = stage.actors
    actor_names = [actor.name for actor in actors]
    all_names = ' '.join(actor_names)
    return f"""
    # 你目睹或者参与了这一切，并更新了你的记忆
    - {movie}
    # 你能确认
    - {all_names} 都还存在。
    """


class Director(Actor):
    def __init__(self, name: str, stage: Stage):
        super().__init__(name)
        self.stage = stage
        print("Director", self.name, "inited")

    def direct(self, script: str)-> str:
        prompt = normal_director(self.stage, script)
        res = self.stage.call_agent(prompt)
        return res
            
    def actor_feedback(self, new_stage_state: str, movie: str)-> str:
        res = actor_feedback_confirm(self, new_stage_state, movie)
        return res



