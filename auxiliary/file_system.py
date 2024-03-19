from auxiliary.components import BackpackComponent

class FileSystem:
    def __init__(self):
        self.backpack = dict()

    def init_backpack_component(self, comp: BackpackComponent):
        self.backpack[comp.owner_name] = set()

    def get_backpack_contents(self, comp: BackpackComponent) -> set:
        return self.backpack.get(comp.owner_name, set())

    def add_content_into_backpack(self, comp: BackpackComponent, item):
        self.backpack.setdefault(comp.owner_name, set()).add(item)

    def remove_from_backpack(self, comp: BackpackComponent, item):
        self.backpack.get(comp.owner_name, set()).remove(item)

    def clear_backpack(self, comp: BackpackComponent):
        self.backpack[comp.owner_name] = set()