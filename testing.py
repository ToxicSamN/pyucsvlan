
import sys
import logging
from datetime import datetime
from logging import handlers
from ucsvlan.vlan import UcsVlan

formatter = logging.Formatter("%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s")
root = logging.getLogger()
root.setLevel(logging.DEBUG)
# handler = logging.handlers.RotatingFileHandler('/var/log/ucs_debug.log',
#                                                mode='a',
#                                                maxBytes=8388608,
#                                                backupCount=8,
#                                                encoding='utf8',
#                                                delay=False)
# handler.setLevel(logging.DEBUG)
# handler.setFormatter(formatter)
# root.addHandler(handler)

dh = logging.StreamHandler(stream=sys.stdout)
dh.setLevel(logging.DEBUG)
dh.setFormatter(formatter)
root.addHandler(dh)

vlan_id = 696
vlan_name = 'v697_VCHB_17.78.16_29'

try:
    root.info('Start UcsVlan')
    # ucs = UcsVlan(ucs=['uycs0319p03','ucs0319p05', 'ucs0319p06', 'ucs0319p07',
    #                    'ucs0319p08', 'ucs0319p11', 'ucs0319p12',
    #                    'ucs0319p15', 'ucs0319p16', 'ucs0319p20', 'ucs0319t04'])
    ucs = UcsVlan(ucs=['ucs0319p03'])
    print("break")
    ucs.update_vlan_list({
        vlan_id: vlan_name
    })
    # vlan_id = 4001
    # vlan_name = 'v4001_prod_vlan_192.168.5.0_24'
    # ucs.update_vlan_list({
    #     vlan_id: vlan_name
    # })
    root.info('Add Vlan')
    ucs.add_vlan(os_env='esx', env='all', sec_env='all')
    root.info('Complete Add Vlan')

    # root.info('Remove Vlan')
    # # ucs = UcsVlan(ucs=['ucs0319p16', 'ucs0319p06', ])
    # ucs = UcsVlan(ucs=['ucs0319t04',])
    # ucs.update_vlan_list({
    #     vlan_id: vlan_name
    # })
    # ucs.remove_vlan(os_env='esx', env='all', sec_env='all', remove_from_cloud=True)
    root.info('Finished adding/removing vlan')
except:
    root.exception('Something went wrong')
print()
