from actor import Actor

#
class Player(Actor):
    def __init__(self, name: str):
        super().__init__(name)
        self.stage = None
        self.description = "一个人类战士，身上的铠甲有些破旧，但是看起来很坚韧。"