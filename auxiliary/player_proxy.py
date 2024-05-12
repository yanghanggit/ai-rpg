from loguru import logger
from typing import List, Optional
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import StageComponent, NPCComponent, PlayerComponent

### 目前啥也不干，但留着有用的时候再用
class PlayerProxy:

    def __init__(self, name: str) -> None:
        self.name = name
        self.clientmessages: List[tuple[str, str]] = []

    def __str__(self) -> str:
        return f'PlayerProxy({self.name})'
    
    def addmessage(self, sender: str, message: str) -> None:
        self.clientmessages.append((sender, message))
        #logger.debug(f"PlayerProxy({self.name}).add_message({sender}, {message})")

    def add_system_message(self, message: str) -> None:
        self.addmessage(f"[system]", message)

    def add_npc_message(self, npcname: str, message: str) -> None:
        self.addmessage(f"[{npcname}]", message)

    def add_stage_message(self, stagename: str, message: str) -> None:
        self.addmessage(f"[{stagename}]", message)

### 目前啥也不干，但留着有用的时候再用
PLAYERS: List[PlayerProxy] = []

### 创建一个玩家代理
def create_player_proxy(playername: str) -> PlayerProxy:
    if get_player_proxy(playername) is not None:
        raise ValueError(f"玩家代理已经存在: {playername}")
    player = PlayerProxy(playername)
    PLAYERS.append(player)
    return player

### 获取一个玩家代理
def get_player_proxy(playername: str) -> Optional[PlayerProxy]:
    for player in PLAYERS:
        if player.name == playername:
            return player
    return None

###################################################################################################################
def add_player_client_message(npcentity: Entity, message: str) -> None:
    if not npcentity.has(PlayerComponent):
        return

    playercomp: PlayerComponent = npcentity.get(PlayerComponent)
    playername: str = playercomp.name
    playerproxy = get_player_proxy(playername)
    if playerproxy is None:
        logger.error(f"notify_player_client, 玩家代理不存在{playername}???")
        return

    #登陆的消息
    npccomp: NPCComponent = npcentity.get(NPCComponent)
    playerproxy.add_npc_message(npccomp.name, message)
###################################################################################################################
### 单人游戏，临时的名字
TEST_PLAYER_NAME = "北京柏林互动科技有限公司"
TEST_LOGIN_INFORMATION = f"""测试的游戏登陆信息"""
TEST_GAME_INSTRUCTIONS_WHEN_LOGIN_SUCCESS_FOR_FIRST_TIME = f"""测试的游戏介绍"""

# f"""
# # 这是一个Demo，叫World2, 规则与要验证的系统如下：
# 1. 过关条件：操作‘无名的复活者’，从‘埃利亚斯·格雷’身上获取‘断指钥匙’，并进入‘灰颜礼拜堂’。
# 2. 初期需要离开‘禁言者之棺’。因为初期player不知道任何游戏相关信息，所以需要通过特殊的命令/prisonbreak离开‘禁言者之棺’。
# 3. 通过和‘埃利亚斯·格雷’的对话来逐步解锁更多信息和可以去的地方。
# 4. 如果发生敌意行为——玩家攻击‘埃利亚斯·格雷’意图夺取钥匙或偷盗被发现，‘摩尔’可能会发起攻击，‘摩尔’的目的就是测试一种‘保护者&随从’的类型。
# 5. ‘好运气先生’会根据场景情况，去惊醒‘鼠王’。这个主要是测试其推理与泛化能力。‘好运气先生’是‘条件触发者’的类型，只不过目前条件写的隐晦。
# 6. ‘鼠王’如被惊醒，就会在所有场景中寻找主角并攻击，玩家则必死无疑。‘鼠王’是‘追击者’的类型。’鼠王‘苏醒就会变成‘鬼抓人’的游戏。
# 7. 唯一克制鼠王的办法是去‘焚化炉‘获取’炉钩‘。"""
    

    


