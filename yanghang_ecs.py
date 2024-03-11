###
### 测试与LLM无关的代码，和一些尝试
###
# import json
# from builder import WorldBuilder, StageBuilder, NPCBuilder



from collections import namedtuple
from entitas import Entity, Matcher, Context, Processors, ExecuteProcessor, ReactiveProcessor, GroupEvent, InitializeProcessor
import time


print('hello python!')

'''
全局变量
'''
running = True
frame_duration = 1 / 30  # 每帧所需时间（30帧每秒）

'''
全局函数
'''
def stop_running():
    global running
    running = False

'''
components
'''
Position = namedtuple('Position', 'x y')
Health = namedtuple('Health', 'value')
Movable = namedtuple('Movable', '')

'''
MyInitializeProcessor
'''
class MyInitializeProcessor(InitializeProcessor):

    def __init__(self, context):
        self._context = context
      
    def initialize(self):
        print('MyInitializeProcessor')
        """
        添加一些entities
        """
        entity = context.create_entity()
        entity.add(Position, 3, 7)
        entity.add(Movable)



'''
MyExecuteProcessor
'''
class MyExecuteProcessor(ExecuteProcessor):

    def __init__(self, context):
        self._context = context
        self._execute_count = 0
       
    def execute(self):
        self._execute_count += 1
        if self._execute_count == 10:
            stop_running()

'''
MyReactiveProcessor
'''
class MyReactiveProcessor(ReactiveProcessor):

    def __init__(self, context):
        super().__init__(context)
        self._context = context

    def get_trigger(self):
        return {Matcher(Movable): GroupEvent.ADDED}

    def filter(self, entity):
        return entity.has(Movable)

    def react(self, entities):
        for entity in entities:
            print('x = ', entity.get(Position).x)
            print('y = ', entity.get(Position).y)
           

'''
执行核心区间
'''
print("Game Start_____________________")

"""
全局上下文
"""
context = Context()

"""
添加一些processors
"""
processors = Processors()
processors.add(MyInitializeProcessor(context))
processors.add(MyExecuteProcessor(context))
processors.add(MyReactiveProcessor(context))

#
processors.activate_reactive_processors()
#processors.initialize()

"""
核心循环
"""
inited = False
while running:

    start_time = time.time()  # 获取当前时间

    if not inited:
        inited = True
        processors.initialize()
        
    processors.execute()
    processors.cleanup()

    end_time = time.time()  # 获取循环结束的时间
    elapsed = end_time - start_time  # 计算循环执行所花费的时间
    if elapsed < frame_duration:
        time.sleep(frame_duration - elapsed)  # 如果循环执行时间小于一帧所需时间，等待剩余时间
 

processors.clear_reactive_processors()
processors.tear_down()

print("Game Over_____________________")










def main():
    print("hello world!")
    pass

    


            

        

if __name__ == "__main__":
    main()