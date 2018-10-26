
from pyucsvlan.credentials import Credential
from pyucsvlan.ucs import Ucs


if __name__ == '__main__':

    ucs_login = {
        'ip': 'ucs0319p09'
    }
    ucs_login.update(
        Credential('oppucs01').get_credential()
    )
    ucs = Ucs(**ucs_login)
    ucs.connect()
    ucs.disconnect()

