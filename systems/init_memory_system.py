from entitas import Entity, Matcher, InitializeProcessor # type: ignore
from auxiliary.components import WorldComponent, StageComponent, NPCComponent, MindVoiceActionComponent
from auxiliary.cn_builtin_prompt import (init_memory_system_prompt)
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from systems.update_archive_helper import UpdareArchiveHelper
from typing import Dict




simulated_memory: Dict[str, str] = {}
simulated_memory['教廷密使'] = """赞美光明！教宗也许是多虑了。任何异变都不可能对教廷产生威胁。即使有。哼哼～也会被我一如既往的‘抹除’掉。"""
simulated_memory['鼠王'] = """嘶嘶嘶。。。。 去吧! 我的子嗣，去吧！为我带来食物！为我监视一切。如果有人背叛我，就让他们知道背叛的代价！嘶嘶嘶！
任何档胆敢进入腐臭地窖的活物，都要被我吃掉！嘶嘶嘶。。。。哦，对了。除了我的小玩应——好运气先生，这个小家伙还是有点用的。如果它叫醒了我，也许是出了什么事。
不过，没关系，嘶嘶嘶，任何的胆敢忤逆我的，都将被我撕成碎片！嘶嘶嘶！！！！"""
simulated_memory['好运气先生'] = """吱吱。。。。格雷和他的该死的狗——摩尔。我讨厌他们，真心讨厌他们！吱吱！！鼠王没吃掉他们，还不是他们定期给鼠王送‘食物’？呵呵。吱吱，无耻的东西！
走着瞧吧！吱吱。。。。早晚有一天他们没用了，鼠王就会吃掉他们，希望到时候他们别瘦的没肉可吃。吱吱。。。。我要时刻盯着他们，因为如果出了问题，鼠王连我也不会放过！吱吱！！
总之，出了任何异常我都会去腐臭地窖叫醒鼠王！吱吱！！"""
simulated_memory['格雷'] = """（阴郁的有气无力的声音）哦，我知道了。。。嗯？这种诅咒的命运我已经习惯了。最近没有给鼠王送食物，他似乎不太高兴。
让我想想。该怎么办呢？要不，把其他的活人骗进腐臭地窖好了(狡诈的坏笑)，嘻嘻嘻嘻。。。那一定很有趣（恶毒的笑声）。。。总之我是不会去的，因为进入腐臭地窖的一定会被鼠王吃掉。"""
simulated_memory['摩尔'] = """（狗叫声）汪汪汪。。。。（狗叫声）汪汪汪。。。。（狗叫声）汪汪汪。。。。"""
simulated_memory['无名的复活者'] = """我知道了。"""

###############################################################################################################################################
class InitMemorySystem(InitializeProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
###############################################################################################################################################
    def initialize(self) -> None:
        self.initmemory()
###############################################################################################################################################
    def initmemory(self) -> None:
        #
        context = self.context
        helper = UpdareArchiveHelper(context)
        helper.prepare()
        #分段处理
        self.handleworld(helper)
        self.handlestages(helper)
        self.handlenpcs(helper)
        ##最后并发执行
        context.agent_connect_system.run_async_requet_tasks()
###############################################################################################################################################
    def handleworld(self, helper: UpdareArchiveHelper) -> None:
        context = self.context
        memory_system = context.memory_system
        agent_connect_system = context.agent_connect_system
        worlds: set[Entity] = context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            worldmemory = memory_system.getmemory(worldcomp.name)
            if worldmemory == "":
                logger.error(f"worldmemory is empty: {worldcomp.name}")
                continue
            prompt = init_memory_system_prompt(worldmemory)
            agent_connect_system.add_human_message_to_chat_history(worldcomp.name, prompt)
            self.simu_mind_voice_response_message(worldcomp.name, context)
            #agent_connect_system.add_async_requet_task(worldcomp.name, readarchprompt)
###############################################################################################################################################
    def handlestages(self, helper: UpdareArchiveHelper) -> None:
        context = self.context
        memory_system = context.memory_system
        agent_connect_system = context.agent_connect_system
        stages: set[Entity] = context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            stagememory = memory_system.getmemory(stagecomp.name)
            if stagememory == "":
                logger.error(f"stagememory is empty: {stagecomp.name}")
                continue
            prompt = init_memory_system_prompt(stagememory)
            #agent_connect_system.add_human_message_to_chat_history(stagecomp.name, prompt)
            #self.simu_mind_voice_response_message(stagecomp.name, context)
            agent_connect_system.add_async_requet_task(stagecomp.name, prompt)
###############################################################################################################################################
    def handlenpcs(self, helper: UpdareArchiveHelper) -> None:
        #
        context = self.context
        memory_system = context.memory_system
        agent_connect_system = context.agent_connect_system
        npcs: set[Entity] = context.get_group(Matcher(all_of=[NPCComponent])).entities
        for npcentity in npcs:
            npccomp: NPCComponent = npcentity.get(NPCComponent)
            npcname: str = npccomp.name
            str_init_memory = memory_system.getmemory(npcname)
            if str_init_memory == "":
                logger.error(f"npcmemory is empty: {npcname}")
                continue
            prompt = init_memory_system_prompt(str_init_memory)
            agent_connect_system.add_human_message_to_chat_history(npcname, prompt)
            # self.simu_mind_voice_response_message(npcname, context)
            agent_connect_system.add_async_requet_task(npcname, prompt)
###############################################################################################################################################
    def simu_mind_voice_response_message(self, name: str, context: ExtendedContext) -> None:
        simu_mind_voice = ""
        if name in simulated_memory:
            simu_mind_voice = simulated_memory[name]
        else:
            simu_mind_voice = f"""我知道了。"""
        message = f"""{{"{MindVoiceActionComponent.__name__}": ["{simu_mind_voice}"]}}"""
        agent_connect_system = context.agent_connect_system
        agent_connect_system.add_ai_message_to_chat_history(name, message)
###############################################################################################################################################
