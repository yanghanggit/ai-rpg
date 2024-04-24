from rpg_game import RPGGame

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class GMCommand:

    def __init__(self, name: str, game: RPGGame) -> None:
        self.name: str = name
        self.game: RPGGame = game
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class GMCommandSimulateRequest(GMCommand):

    def __init__(self, name: str, game: RPGGame, targetname: str, content: str) -> None:
        super().__init__(name, game)
        self.targetname = targetname
        self.content = content

    def execute(self) -> None:
        self.game.extendedcontext.agent_connect_system.request(self.targetname, self.content)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class GMCommandSimulateRequestThenRemoveConversation(GMCommand):

    def __init__(self, name: str, game: RPGGame, targetname: str, content: str) -> None:
        super().__init__(name, game)
        self.targetname = targetname
        self.content = content

    def execute(self) -> None:
        context = self.game.extendedcontext
        name = self.targetname
        agent_connect_system = context.agent_connect_system
        reponse = agent_connect_system.request(name, self.content)
        if reponse is not None:
            agent_connect_system.remove_last_conversation_between_human_and_ai(name)
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
