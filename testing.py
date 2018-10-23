
from pyucsvlan.vnic.template import VnicTemplate
from pyucsvlan.credentials import Credential
from pyucsvlan.lancloud.vlan import Vlan
from pyucsvlan.ucs import Ucs
from ucsmsdk.ucshandle import UcsHandle


if __name__ == '__main__':

    ucs_login = {
        'ip': 'ucs0319t04'
    }
    ucs_login.update(
        Credential('oppucs01').get_credential()
    )
    ucs = Ucs(**ucs_login)
    ucs.connect()
    ucs.disconnect()

