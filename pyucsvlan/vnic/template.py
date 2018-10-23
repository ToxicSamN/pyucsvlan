
from pyucsvlan.lancloud.vlan import Vlan
from pyucsvlan.vnic import Vnic


class VnicTemplate(Vnic):

    def __init__(self, *args, **kwargs):
        self.managed_object = 'MO'
        super().__init__(*args, **kwargs)


