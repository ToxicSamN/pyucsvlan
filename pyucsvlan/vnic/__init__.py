

class Vnic:

    def __init__(self, ucs):
        self.name = None
        self.vlans = None
        self.managed_object = None
        self.ucs = ucs
        print(ucs)

    def add_vlan(self):
        return self

    def remove_vlan(self):
        return self
