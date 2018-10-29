
import datetime
from pyucs.credentials import Credential
from pyucs.ucs import Ucs
from pyucs.statsd.collector import StatsCollector


def pool_func(pool_args):
    ucs, data, data_type = pool_args

    if data_type == 'vnic':
        return ucs.get_vnic_stats(data)
    elif data_type == 'vhba':
        return ucs.get_vhba_stats(data)


if __name__ == '__main__':

    ucs_login = {
        'ip': 'ucs0319p05'
    }
    ucs_login.update(
        Credential('oppucs01').get_credential()
    )
    ucs = Ucs(**ucs_login)
    print(datetime.datetime.now())
    ucs.connect()
    print(datetime.datetime.now())
    statsd = StatsCollector(ucs)
    statsd.query_stats()
    print(datetime.datetime.now())
    ucs.disconnect()
