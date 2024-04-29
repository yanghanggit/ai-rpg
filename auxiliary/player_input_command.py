from entitas import Entity #type: ignore
from rpg_game import RPGGame
from loguru import logger
from auxiliary.components import (
    BroadcastActionComponent,
    PlayerAwakeActionComponent,
    SpeakActionComponent, 
    StageComponent, 
    NPCComponent, 
    FightActionComponent, 
    PlayerComponent, 
    LeaveForActionComponent, 
    WhisperActionComponent,
    SearchActionComponent,
    PrisonBreakActionComponent,
    PerceptionActionComponent,
    StealActionComponent,
    TradeActionComponent, 
    CheckStatusActionComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.player_proxy import PlayerProxy
from abc import ABC, abstractmethod


TEST_GAME_INSTRUCTIONS_WHEN_LOGIN_SUCCESS_FOR_FIRST_TIME = """
# 游戏世界设定
- 这是一个基于西方中世纪奇幻设定，并在叙事规则与文本风格上是“H.P。 Lovecraft克拉夫特式恐怖”的角色扮演游戏
## 密执安（Mithran）
名为密执安的城市，由于一场未知的疫病爆发而与外界隔绝。这场疫病不仅迫使城市的大门紧闭，数十年来无人能进出，而且这种封闭似乎被某种超自然力量加以强化，使得密执安成为了一个完全独立且孤立的世界。疫病不仅带来了死亡，还在城市中播下了变异与疯狂的种子，让城市的生存环境变得更加险恶和不可预测。密执安的历史迷雾重重，其存在远远超出了居民们的记忆。这座城市由高大的城墙所包围，内有错综复杂的街道和充满古老气息的建筑。每一块石头和每一座塔楼都似乎隐藏着古老的秘密。有传言说，城市之下藏有一座古老的遗迹，其中存放着揭示宇宙真相的禁忌知识。这场神秘的疫病不仅带来了生理上的变异，还让许多居民在精神上陷入了疯狂。魔法在这个城市中是真实存在的，但它往往与疫病的影响交织在一起，变得异常危险且难以控制。城市及其周边地区潜伏着由魔法或疫病造就的各种怪兽，这些怪兽或许是城市古老诅咒的一部分，或是从更黑暗的地方爬出来的。尽管密执安被疫病和超自然力量封闭，但城市内部仍存在着不同的利益团体和派系。这些团体或许有着自己的秘密、目标和资源。他们在暗中争斗，不仅为了争夺有限的资源和权力，还试图找到或控制能够解决或利用疫病的秘密。
## 圣灰园（Sanctum Cinis）
在密执安的边缘，圣灰园融合了公墓和焚化厂的双重身份，由城市中最古老的教会组织管理。位于城市与外界的模糊边界，这个设施包含着被厚重雾气笼罩的“灰颜墓地”，其中墓碑排列错落，有的年代久远，名字已模糊不清，这里安息着那些正常死亡的居民。与之形成鲜明对比的是“焚化炉”，一座巨大的石结构，其烟囱不断升腾的烟雾标志着它从未停歇的工作，处理疫病死者的遗体，以防疫病的进一步传播。除此之外，圣灰园还包括“灰颜礼拜堂”和“腐臭地窖”，灰颜礼拜堂为寻求慰藉的灵魂提供安宁之地，腐臭地窖里有着圣灰园不为人知的可怕秘密。
"""

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommand(ABC):

    def __init__(self, inputname: str, game: RPGGame, playerproxy: PlayerProxy) -> None:
        self.inputname: str = inputname
        self.game: RPGGame = game
        self.playerproxy: PlayerProxy = playerproxy

    @abstractmethod
    def execute(self) -> None:
        pass

    # 为了方便，直接在这里添加消息，不然每个子类都要写一遍
    def add_human_message(self, entity: Entity, newmsg: str) -> None:
        context = self.game.extendedcontext
        context.safe_add_human_message_to_entity(entity, newmsg)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandLogin(PlayerCommand):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, login_npc_name: str) -> None:
        super().__init__(name, game, playerproxy)
        self.login_npc_name = login_npc_name

    def execute(self) -> None:
        context = self.game.extendedcontext
        login_npc_name = self.login_npc_name
        myname = self.playerproxy.name
        logger.debug(f"{self.inputname}, player name: {myname}, target name: {login_npc_name}")

        npcentity = context.getnpc(login_npc_name)
        if npcentity is None:
            # 扮演的角色，本身就不存在于这个世界
            logger.error(f"{login_npc_name}, npc is None, login failed")
            return

        playerentity = context.getplayer(myname)
        if playerentity is not None:
            # 已经登陆完成
            logger.error(f"{myname}, already login")
            return
        
        playercomp: PlayerComponent = npcentity.get(PlayerComponent)
        if playercomp is None:
            # 扮演的角色不是设定的玩家可控制NPC
            logger.error(f"{login_npc_name}, npc is not player ctrl npc, login failed")
            return
        
        if playercomp.name != "" and playercomp.name != myname:
            # 已经有人控制了，但不是你
            logger.error(f"{login_npc_name}, player already ctrl by some player {playercomp.name}, login failed")
            return
    
        npcentity.replace(PlayerComponent, myname)
        logger.info(f"login success! {myname} => {login_npc_name}")
        
        ####
        clientmessage = self.test_client_message_after_login_success()
        logger.warning(f"{myname} 登陆了游戏")

        ## 登录之后，客户端需要看到的消息
        if npcentity.has(PlayerAwakeActionComponent):
            logger.error(f"{login_npc_name} already has AwakeActionComponent?")
            npcentity.remove(PlayerAwakeActionComponent)
        #
        action = ActorAction(login_npc_name, PlayerAwakeActionComponent.__name__, [f"{clientmessage}", TEST_GAME_INSTRUCTIONS_WHEN_LOGIN_SUCCESS_FOR_FIRST_TIME])
        npcentity.add(PlayerAwakeActionComponent, action)
        
    ##这是一个测试的方法，目前登陆成功后，就是把memory给到，后续可以做的复杂一些
    def test_client_message_after_login_success(self) -> str:
        context = self.game.extendedcontext
        memory_system = context.memory_system
        npcentity = context.getnpc(self.login_npc_name)
        assert npcentity is not None
        safename = context.safe_get_entity_name(npcentity)
        return memory_system.getmemory(safename)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class PlayerCommandAttack(PlayerCommand):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, attack_target_name: str) -> None:
        super().__init__(name, game, playerproxy)
        self.attack_target_name = attack_target_name

    def execute(self) -> None:
        context = self.game.extendedcontext 
        attack_target_name = self.attack_target_name
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_attack: player is None")
            return

        if playerentity.has(NPCComponent):
            npccomp: NPCComponent = playerentity.get(NPCComponent)
            action = ActorAction(npccomp.name, FightActionComponent.__name__, [attack_target_name])
            playerentity.add(FightActionComponent, action)

        elif playerentity.has(StageComponent):
            stagecomp: StageComponent = playerentity.get(StageComponent)
            action = ActorAction(stagecomp.name, FightActionComponent.__name__, [attack_target_name])
            playerentity.add(FightActionComponent, action)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class PlayerCommandLeaveFor(PlayerCommand):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, target_stage_name: str) -> None:
        super().__init__(name, game, playerproxy)
        self.target_stage_name = target_stage_name

    def execute(self) -> None:
        context = self.game.extendedcontext
        target_stage_name = self.target_stage_name
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_leave: player is None")
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, LeaveForActionComponent.__name__, [target_stage_name])
        playerentity.add(LeaveForActionComponent, action)

        newmsg = f"""{{"{LeaveForActionComponent.__name__}": ["{target_stage_name}"]}}"""
        self.add_human_message(playerentity, newmsg)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class PlayerCommandPrisonBreak(PlayerCommand):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy) -> None:
        super().__init__(name, game, playerproxy)

    def execute(self) -> None:
        context = self.game.extendedcontext
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_leave: player is None")
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        current_stage_name: str = npccomp.current_stage
        stageentity = context.getstage(current_stage_name)
        if stageentity is None:
            logger.error(f"PrisonBreakActionSystem: {current_stage_name} is None")
            return

        action = ActorAction(npccomp.name, PrisonBreakActionComponent.__name__, [current_stage_name])
        playerentity.add(PrisonBreakActionComponent, action)
        
        newmsg = f"""{{"{PrisonBreakActionComponent.__name__}": ["{current_stage_name}"]}}"""
        self.add_human_message(playerentity, newmsg)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandBroadcast(PlayerCommand):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, content: str) -> None:
        super().__init__(name, game, playerproxy)
        self.content = content

    def execute(self) -> None:
        context = self.game.extendedcontext
        content = self.content
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_broadcast: player is None")
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, BroadcastActionComponent.__name__, [content])
        playerentity.add(BroadcastActionComponent, action)
       
        newmsg = f"""{{"{BroadcastActionComponent.__name__}": ["{content}"]}}"""
        self.add_human_message(playerentity, newmsg)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandSpeak(PlayerCommand):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, speakcontent: str) -> None:
        super().__init__(name, game, playerproxy)
        self.speakcontent = speakcontent

    def execute(self) -> None:
        context = self.game.extendedcontext
        speakcontent = self.speakcontent
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_speak: player is None")
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, SpeakActionComponent.__name__, [speakcontent])
        playerentity.add(SpeakActionComponent, action)
        
        newmsg = f"""{{"{SpeakActionComponent.__name__}": ["{speakcontent}"]}}"""
        self.add_human_message(playerentity, newmsg)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandWhisper(PlayerCommand):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, whispercontent: str) -> None:
        super().__init__(name, game, playerproxy)
        self.whispercontent = whispercontent

    def execute(self) -> None:
        context = self.game.extendedcontext
        whispercontent = self.whispercontent
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_whisper: player is None")
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, WhisperActionComponent.__name__, [whispercontent])
        playerentity.add(WhisperActionComponent, action)

        newmemory = f"""{{"{WhisperActionComponent.__name__}": ["{whispercontent}"]}}"""
        self.add_human_message(playerentity, newmemory)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandSearch(PlayerCommand):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, search_target_prop_name: str) -> None:
        super().__init__(name, game, playerproxy)
        # todo: 这里search_target_prop_name需要判断是否为合理道具，现在会全部进行寻找。
        self.search_target_prop_name = search_target_prop_name

    def execute(self) -> None:
        context = self.game.extendedcontext
        # todo:道具如果是唯一性，怎么检测？
        search_target_prop_name = self.search_target_prop_name
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            logger.warning("debug_search: player is None")
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, SearchActionComponent.__name__, [search_target_prop_name])
        playerentity.add(SearchActionComponent, action)

        newmemory = f"""{{"{SearchActionComponent.__name__}": ["{search_target_prop_name}"]}}"""
        self.add_human_message(playerentity, newmemory)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandPerception(PlayerCommand):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy) -> None:
        super().__init__(name, game, playerproxy)
        

    def execute(self) -> None:
        context = self.game.extendedcontext
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, PerceptionActionComponent.__name__, [npccomp.current_stage])
        playerentity.add(PerceptionActionComponent, action)

        newmemory = f"""{{"{PerceptionActionComponent.__name__}": ["{npccomp.current_stage}"]}}"""
        self.add_human_message(playerentity, newmemory)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandSteal(PlayerCommand):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, command: str) -> None:
        super().__init__(name, game, playerproxy)
        # "@要偷的人>偷他的啥东西"
        self.command = command

    def execute(self) -> None:
        context = self.game.extendedcontext
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, StealActionComponent.__name__, [self.command])
        playerentity.add(StealActionComponent, action)

        newmemory = f"""{{"{StealActionComponent.__name__}": ["{self.command}"]}}"""
        self.add_human_message(playerentity, newmemory)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandTrade(PlayerCommand):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy, command: str) -> None:
        super().__init__(name, game, playerproxy)
        # "@交易的对象>我的啥东西"
        self.command = command

    def execute(self) -> None:
        context = self.game.extendedcontext
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            return
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, TradeActionComponent.__name__, [self.command])
        playerentity.add(TradeActionComponent, action)

        newmemory = f"""{{"{TradeActionComponent.__name__}": ["{self.command}"]}}"""
        self.add_human_message(playerentity, newmemory)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerCommandCheckStatus(PlayerCommand):

    def __init__(self, name: str, game: RPGGame, playerproxy: PlayerProxy) -> None:
        super().__init__(name, game, playerproxy)

    def execute(self) -> None:
        context = self.game.extendedcontext
        playerentity = context.getplayer(self.playerproxy.name)
        if playerentity is None:
            return
        
        if playerentity.has(CheckStatusActionComponent):
            playerentity.remove(CheckStatusActionComponent)
        
        npccomp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, CheckStatusActionComponent.__name__, [npccomp.name])
        playerentity.add(CheckStatusActionComponent, action)

        newmemory = f"""{{"{CheckStatusActionComponent.__name__}": ["{npccomp.name}"]}}"""
        self.add_human_message(playerentity, newmemory)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
