
import time
import queue
import multiprocessing
from datetime import datetime
from pyucs.credentials import Credential
from pyucs.ucs import Ucs
from pyucs.statsd.collector import StatsCollector
from pyucs.statsd.parse import Parser
from pyucs.influx import InfluxDB


def q_watcher(q1, q2, out_q):
    s_time = datetime.now()
    while True:
        time_delta = (datetime.now()) - s_time
        if q1.qsize() > 0 or q2.qsize() > 0:
            out_q.put_nowait("iq_size: {}, sq_size: {}".format(q1.qsize(), q2.qsize()))

        if time_delta.seconds > 60:
            break


def pool_func(pool_args):
    ucs, data, data_type = pool_args

    if data_type == 'vnic':
        return ucs.get_vnic_stats(data)
    elif data_type == 'vhba':
        return ucs.get_vhba_stats(data)


if __name__ == '__main__':
    queue_manager = multiprocessing.Manager()
    sq = queue_manager.Queue()
    iq = queue_manager.Queue()
    oq = queue_manager.Queue()
    tq = queue_manager.Queue()

    parse_proc = multiprocessing.Process(target=Parser, kwargs={'statsq': sq, 'influxq': iq})
    influx_proc = multiprocessing.Process(target=InfluxDB, kwargs={'influxq': iq,
                                                                            'host': 'y0319t11434',
                                                                            'port': 8086,
                                                                            'username': 'anonymous',
                                                                            'password': 'anonymous',
                                                                            'database': 'perf_stats',
                                                                            'timeout': 5,
                                                                            'retries': 3
                                                                            }
                                          )
    parse_proc.start()
    influx_proc.start()
    watcher_proc = multiprocessing.Process(target=q_watcher, args=(iq, sq, oq,))
    watcher_proc.start()

    ucs_login = {
        'ip': 'ucs0319t04'
    }
    ucs_login.update(
        Credential('oppucs01').get_credential()
    )

    ucs = Ucs(**ucs_login)
    tq.put_nowait("Start connect: {}".format(datetime.now()))
    ucs.connect()
    tq.put_nowait("Start statsd: {}".format(datetime.now()))
    statsd = StatsCollector(ucs)
    statsd.query_stats(sq)
    tq.put_nowait("End statsd: {}".format(datetime.now()))

    while watcher_proc.is_alive():
        try:
            data = oq.get_nowait()
            print(data)
        except queue.Empty:
            pass

    ucs.disconnect()
    parse_proc.terminate()
    influx_proc.terminate()
    watcher_proc.terminate()
    tq.put_nowait("End Program: {}".format(datetime.now()))

    while True:
        try:
            print(tq.get_nowait())
        except queue.Empty:
            break
